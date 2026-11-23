"""Shared data: BO registry, BNPB import and daily air-quality processing."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
import hashlib,json,os,re,tempfile,time,uuid
import numpy as np
import pandas as pd


FIELDS=['BO','Alamat','Kecamatan','Kabupaten/Kota','Provinsi']

def normalized(value):
    return re.sub(r'\s+',' ',str(value).strip()).casefold()

def valid_code(value):
    value=str(value).strip()
    if re.fullmatch(r'\d{4}\.0',value): value=value[:-2]
    if re.fullmatch(r'\d{2}\.\d{2}',value): value=value.replace('.','')
    return value if re.fullmatch(r'\d{4}',value) else ''

def region_aliases(value):
    name=normalized(value)
    aliases={name,name.replace('kota administrasi ','kota adm. '),name.replace('kota administrasi ','kota ')}
    if name.startswith('kabupaten '): aliases.add(name[len('kabupaten '):])
    elif not name.startswith(('kota ','kota adm. ')): aliases.add('kabupaten '+name)
    if name in {'kota administrasi jakarta selatan','kota jakarta selatan'}: aliases.add('jakarta selatan')
    return aliases

def registry_path(path=None):
    return Path(path or os.environ.get('BCP_CUSTOM_BO_PATH') or Path(__file__).parent/'data'/'custom_branches.json')

def read_custom(path=None):
    path=registry_path(path)
    if not path.exists(): return []
    try: records=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as exc: raise ValueError('Daftar BO tambahan tidak dapat dibaca. Periksa file '+str(path)) from exc
    if not isinstance(records,list) or any(not isinstance(r,dict) or not all(str(r.get(f,'')).strip() for f in FIELDS) or not r.get('bo_id') for r in records):
        raise ValueError('Format daftar BO tambahan tidak valid: '+str(path))
    names=[normalized(r['BO']) for r in records]
    if len(set(names))!=len(names) or len({r['bo_id'] for r in records})!=len(records):
        raise ValueError('Nama atau identitas BO tambahan ganda: '+str(path))
    return records

@contextmanager
def _locked(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with open(str(path)+'.lock','a+b') as handle:
        handle.seek(0);handle.write(b'0');handle.flush()
        deadline=time.monotonic()+5
        while True:
            try:
                handle.seek(0)
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()>deadline: raise ValueError('Daftar BO sedang diperbarui pengguna lain. Coba simpan lagi.')
                time.sleep(.05)
        try: yield
        finally:
            handle.seek(0)
            if os.name=='nt': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle,fcntl.LOCK_UN)

def add_branch(values,builtin,path=None):
    record={f:re.sub(r'\s+',' ',str(values.get(f,'')).strip()) for f in FIELDS}
    limits={'BO':100,'Alamat':1000,'Kecamatan':150,'Kabupaten/Kota':150,'Provinsi':150}
    for field in FIELDS:
        if not record[field]: raise ValueError(field+' wajib diisi.')
        if len(record[field])>limits[field]: raise ValueError(field+' terlalu panjang.')
        if any(ord(c)<32 for c in record[field]): raise ValueError(field+' mengandung karakter tidak valid.')
    path=registry_path(path)
    with _locked(path):
        records=read_custom(path)
        existing=list(builtin['BO'])+[r['BO'] for r in records]
        if normalized(record['BO']) in {normalized(n) for n in existing}:
            raise ValueError('Nama BO sudah digunakan. Gunakan nama BO yang berbeda.')
        record.update({'bo_id':'BO-'+uuid.uuid4().hex[:12],'ID Kabupaten':'','BO tambahan':True,
            'Regional':'Belum ditetapkan','Wilayah':'Belum ditetapkan','Latitude':None,'Longitude':None,
            'Status kecamatan':'Diisi pengguna','Dibuat':datetime.now(timezone.utc).isoformat()})
        records.append(record)
        descriptor,tmp=tempfile.mkstemp(prefix=path.stem+'-',suffix='.tmp',dir=path.parent)
        try:
            with os.fdopen(descriptor,'w',encoding='utf-8') as handle:
                json.dump(records,handle,ensure_ascii=False,indent=2);handle.flush();os.fsync(handle.fileno())
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
    return record

def resolved_master(base,raw=None,path=None):
    records=[]
    for row in base.to_dict('records'):
        row.update({'BO tambahan':False,'Status pemetaan':'Master BO terpetakan'})
        records.append(row)
    extras=read_custom(path)
    if {normalized(r['BO']) for r in records}&{normalized(r['BO']) for r in extras}:
        raise ValueError('Nama BO tambahan bertabrakan dengan master awal.')
    candidates=[]
    if raw is not None and {'ID Kabupaten','Kabupaten','Provinsi'}.issubset(raw.columns):
        candidates=[(valid_code(r['ID Kabupaten']),normalized(r.Kabupaten),normalized(r.Provinsi))
            for _,r in raw[['ID Kabupaten','Kabupaten','Provinsi']].drop_duplicates().iterrows()]
    for extra in extras:
        row=dict(extra)
        aliases=region_aliases(row['Kabupaten/Kota']);province=normalized(row['Provinsi'])
        matches={rid for rid,name,p in candidates if rid and name in aliases and p==province}
        if raw is None:
            matches={valid_code(r['ID Kabupaten']) for r in records
                if region_aliases(r['Kabupaten/Kota'])&aliases and normalized(r['Provinsi'])==province and valid_code(r['ID Kabupaten'])}
        row['ID Kabupaten']=next(iter(matches)) if len(matches)==1 else ''
        row['Status pemetaan']=('Cocok dengan data BNPB' if raw is not None else 'Cocok dengan master wilayah') if len(matches)==1 else ('Nama wilayah ambigu pada BNPB' if len(matches)>1 else 'Wilayah belum ditemukan pada BNPB' if raw is not None else 'Menunggu data BNPB')
        records.append(row)
    result=pd.DataFrame(records)
    for name in result.columns.difference(['Latitude','Longitude']): result[name]=result[name].fillna('')
    for name in ['Latitude','Longitude']:
        result[name]=pd.to_numeric(result[name],errors='coerce')
    result['Pemetaan tersedia']=result['ID Kabupaten'].map(valid_code).ne('')
    return result

def master_signature(master):
    return hashlib.sha256(master.to_json(orient='records',force_ascii=False).encode()).hexdigest()

IMPACTS = ["Meninggal", "Hilang", "Terluka", "Rumah Rusak", "Rumah Terendam", "Fasum Rusak"]

CORE = ["ID Kabupaten", "Tanggal Kejadian", "Kejadian", "Kabupaten", "Provinsi"]

HAZARDS = ["Banjir", "Cuaca ekstrem", "Karhutla", "Tanah longsor", "Gempa bumi", "Gelombang pasang dan abrasi", "Erupsi gunung api", "Tsunami"]

HAZARD_MAP = dict(zip(["BANJIR","CUACA EKSTREM","KEBAKARAN HUTAN DAN LAHAN","TANAH LONGSOR","GEMPABUMI","GELOMBANG PASANG DAN ABRASI","ERUPSI GUNUNG API","TSUNAMI"], HAZARDS))

def branches(raw=None):
    base=pd.DataFrame(json.loads((Path(__file__).parent/'data'/'branches.json').read_text(encoding='utf-8'))).fillna('')
    return resolved_master(base,raw)

def norm(value):
    return re.sub(r'\s+', ' ', str(value).strip()).casefold()

def code(value):
    if pd.isna(value): return ''
    text=str(value).strip()
    if re.fullmatch(r'\d{4}\.0',text): text=text[:-2]
    elif re.fullmatch(r'\d{2}\.\d{2}',text): text=text.replace('.','')
    return text if re.fullmatch(r'\d{4}',text) else ''

def workbook_layout(content):
    book=pd.ExcelFile(BytesIO(content),engine='openpyxl')
    candidates=[]
    for name in book.sheet_names:
        preview=pd.read_excel(book,sheet_name=name,header=None,nrows=12)
        for index,row in preview.iterrows():
            values={norm(v) for v in row if pd.notna(v)}
            if all(norm(c) in values for c in CORE):
                candidates.append({'sheet':name,'header':int(index)})
                break
    return candidates, book.sheet_names

def read_source(content,name,sheet=None,header=None):
    if name.lower().endswith('.csv'):
        df=pd.read_csv(BytesIO(content),sep=None,engine='python',keep_default_na=False)
        sheet='CSV'; header=0
    else:
        candidates,_=workbook_layout(content)
        chosen=next((c for c in candidates if c['sheet']==sheet),None) if sheet else next(iter(candidates),None)
        if chosen is None: raise ValueError('Tidak ditemukan tabel detail BNPB. Dibutuhkan tanggal, kejadian, ID kabupaten, kabupaten, dan provinsi. Pivot Count tidak dapat dipakai sebagai data kejadian.')
        sheet=chosen['sheet']; header=chosen['header'] if header is None else header
        df=pd.read_excel(BytesIO(content),sheet_name=sheet,header=header,engine='openpyxl',keep_default_na=False)
    df.columns=[str(c).strip() for c in df.columns]
    if df.columns.duplicated().any(): raise ValueError('Judul kolom duplikat. Perbaiki file sumber sebelum diimpor.')
    rename={c:next((k for k in CORE+IMPACTS+['No.','Kode Identitas Bencana','Lokasi','Penyebab','Kronologi & Dokumentasi'] if norm(k)==norm(c)),c) for c in df.columns}
    df=df.rename(columns=rename)
    if df.columns.duplicated().any(): raise ValueError('Nama kolom duplikat setelah normalisasi.')
    missing=[c for c in CORE if c not in df]
    if missing: raise ValueError('Kolom wajib tidak ditemukan: '+', '.join(missing))
    df.insert(0,'Baris sumber',range(header+2,header+2+len(df)))
    return df, {'sheet':sheet,'header':header+1,'sha256':hashlib.sha256(content).hexdigest(),'file':name}

@dataclass
class ImportResult:
    raw: pd.DataFrame
    events: pd.DataFrame
    rejected: pd.DataFrame
    impact_issues: pd.DataFrame
    duplicate_extra: int
    invalid_empty_rows: int

def prepare(raw, start, end, remove_identical=False, master=None):
    df=raw.copy()
    nonempty=~df[[c for c in df if c!='Baris sumber']].apply(lambda col: col.isna() | col.astype(str).str.strip().eq('')).all(axis=1)
    empty=int((~nonempty).sum()); df=df[nonempty].copy()
    issues=pd.Series('',index=df.index,dtype='str')
    def reject(mask,reason):
        issues.loc[mask]=issues.loc[mask]+reason+'; '
    text=df['Tanggal Kejadian'].astype(str).str.strip()
    iso=text.str.match(r'^\d{4}-\d{2}-\d{2}(?:[ T].*)?$')
    dates=pd.to_datetime(text,format='mixed',dayfirst=True,errors='coerce')
    dates.loc[iso]=pd.to_datetime(text[iso],format='ISO8601',errors='coerce')
    df['Tanggal']=dates.dt.normalize()
    df['Kode wilayah']=df['ID Kabupaten'].map(code)
    reject(df.Tanggal.isna(),'Tanggal tidak valid')
    reject(df['Kode wilayah'].eq(''),'ID Kabupaten tidak valid (butuh 4 digit)')
    for c in ['Kejadian','Kabupaten','Provinsi']:
        reject(df[c].isna() | df[c].astype(str).str.strip().eq(''), c+' kosong')
    reject(df.Tanggal.notna() & ~df.Tanggal.between(pd.Timestamp(start),pd.Timestamp(end)),'Di luar periode terpilih')
    master=branches(raw) if master is None else master
    master=master[master['ID Kabupaten'].ne('')].drop_duplicates('ID Kabupaten').set_index('ID Kabupaten')
    for rid,b in master.iterrows():
        selected=df['Kode wilayah'].eq(rid)
        expected_name=norm(b['Kabupaten/Kota'])
        aliases=region_aliases(b['Kabupaten/Kota'])
        if rid=='3174': aliases.update({'kota jakarta selatan','jakarta selatan'})
        # BNPB labels Kabupaten Banjar as Banjar; both refer to ID 6303.
        if rid=='6303': aliases.update({'banjar','kabupaten banjar'})
        wrong=selected & (~df.Kabupaten.map(norm).isin(aliases) | df.Provinsi.map(norm).ne(norm(b.Provinsi)))
        reject(wrong,'Kode wilayah bertentangan dengan nama/provinsi master BO')
    df['Bencana']=df.Kejadian.astype(str).str.strip().str.upper().map(lambda v:HAZARD_MAP.get(v,v.title()))
    reject(df['Bencana'].map(norm).eq('kekeringan'),'Kategori di luar cakupan BCP: Kekeringan')
    fingerprint_cols=[c for c in raw if c not in ['No.','Baris sumber']]
    df['Identik tambahan']=df.duplicated(subset=fingerprint_cols,keep='first')
    df['Grup identik']=df.duplicated(subset=fingerprint_cols,keep=False)
    duplicate_extra=int(df.loc[issues.eq(''),'Identik tambahan'].sum())
    if remove_identical: reject(df['Identik tambahan'],'Duplikat identik tambahan (opsi pengguna)')
    df['Masalah']=issues.str.rstrip('; ')
    rejected=df[issues.ne('')].copy()
    good=df[issues.eq('')].copy()
    impact_issues=[]
    for c in IMPACTS:
        present=c in good
        if not present:
            good[c]=pd.NA
            impact_issues.append({'Baris sumber':None,'Kolom':c,'Nilai asli':'Kolom tidak ada','Masalah':'Kolom wajib untuk penilaian impact tidak tersedia; bukan nol'})
        raw_values=good[c].copy()
        blank=raw_values.isna() | raw_values.astype(str).str.strip().eq('')
        converted=blank & present
        good[c+' kosong menjadi 0']=converted
        numeric=pd.to_numeric(raw_values.mask(converted,0),errors='coerce')
        invalid=((~blank & numeric.isna()) | numeric.lt(0) | (numeric.notna() & numeric.mod(1).ne(0))).fillna(False)
        for i in good.index[invalid]:
            impact_issues.append({'Baris sumber':good.at[i,'Baris sumber'],'Kolom':c,'Nilai asli':str(raw_values.at[i]),'Masalah':'Bukan jumlah bulat nonnegatif; ditampilkan tidak tersedia'})
        good[c]=numeric.mask(invalid).astype('Float64')
    good['Tahun']=good.Tanggal.dt.year
    good['Bulan']=good.Tanggal.dt.to_period('M').astype(str)
    good['Tanggal/wilayah/jenis sama']=good.duplicated(['Tanggal','Kode wilayah','Bencana'],keep=False)
    return ImportResult(raw,good.reset_index(drop=True),rejected.reset_index(drop=True),pd.DataFrame(impact_issues),duplicate_extra,empty)

def bcp_events(events):
    return events.loc[~events['Bencana'].map(norm).eq('kekeringan')].copy()

def match_branches(events,master=None):
    events=bcp_events(events)
    master=branches() if master is None else master
    master=master.loc[master['ID Kabupaten'].ne(''),['bo_id','BO','ID Kabupaten','Kabupaten/Kota','Wilayah']]
    return events.merge(master,left_on='Kode wilayah',right_on='ID Kabupaten',how='inner',validate='many_to_many',suffixes=('',' master'))

def summary(events, master=None):
    master=branches() if master is None else master
    matched=match_branches(events,master)
    out=master[['bo_id','BO','Kabupaten/Kota','ID Kabupaten','Provinsi','Wilayah']].copy()
    counts=matched.groupby('bo_id').size()
    out['Catatan kejadian']=out.bo_id.map(counts).fillna(0).astype(int)
    for metric in IMPACTS:
        totals=matched.groupby('bo_id')[metric].sum(min_count=1)
        out[metric]=out.bo_id.map(totals)
        out[metric+' terisi']=out.bo_id.map(matched.groupby('bo_id')[metric].count()).fillna(0).astype(int)
    out['Keterangan']=out['Catatan kejadian'].map(lambda x:'Ada catatan pada filter' if x else 'Tidak ada catatan pada filter; bukan bukti nihil risiko')
    return out

def impact_total(events,metric):
    return events[metric].sum(min_count=1),int(events[metric].notna().sum()),len(events)

def monthly(events,start,end):
    months=pd.period_range(start,end,freq='M').astype(str)
    counts=events.groupby('Bulan').size().reindex(months,fill_value=0)
    return counts.rename_axis('Bulan').reset_index(name='Catatan kejadian')

def heatmap(events,master,hazards):
    matched=match_branches(events,master)
    if matched.empty: return pd.DataFrame(0,index=master.BO,columns=hazards)
    return pd.crosstab(matched.BO,matched.Bencana).reindex(index=master.BO,columns=hazards,fill_value=0)

def csv_bytes(frame):
    df=frame.copy()
    for c in df:
        if pd.api.types.is_string_dtype(df[c].dtype) or df[c].dtype==object:
            df[c]=df[c].map(lambda v: "'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
    return df.to_csv(index=False).encode('utf-8-sig')

AIR_METRIC='Dampak Udara'

AIR_COLUMNS=['Kabupaten/Kota','Tanggal','Kualitas Udara']

@dataclass
class AirImport:
    raw: pd.DataFrame
    daily: pd.DataFrame
    issues: pd.DataFrame
    meta: dict

def parse_dates(values):
    text=values.astype(str).str.strip()
    iso=text.str.match(r'^\d{4}-\d{2}-\d{2}')
    dates=pd.to_datetime(text,format='mixed',dayfirst=True,errors='coerce')
    dates.loc[iso]=pd.to_datetime(text[iso],format='ISO8601',errors='coerce')
    serial=pd.to_numeric(values,errors='coerce')
    excel=serial.between(20000,80000)
    dates.loc[excel]=pd.to_datetime(serial[excel],unit='D',origin='1899-12-30')
    return dates.dt.normalize()

def prepare_air(raw,master,meta=None):
    raw=raw.copy()
    missing=set(AIR_COLUMNS)-set(raw.columns)
    if missing: raise ValueError('Kolom kualitas udara belum lengkap: '+', '.join(sorted(missing)))
    candidates={}
    for _,bo in master.iterrows():
        rid=valid_code(bo['ID Kabupaten'])
        if not rid: continue
        name=norm(bo['Kabupaten/Kota'])
        for alias in region_aliases(name)|{re.sub(r'^(kota administrasi|kota|kabupaten) ','',name)}:
            candidates.setdefault(alias,set()).add(rid)
    aliases={name:next(iter(ids)) for name,ids in candidates.items() if len(ids)==1}
    work=pd.DataFrame(index=raw.index)
    work['Kabupaten/Kota']=raw['Kabupaten/Kota'].astype(str).str.strip()
    work['Kode wilayah']=work['Kabupaten/Kota'].map(norm).map(aliases)
    work['Tanggal']=parse_dates(raw.Tanggal)
    values=pd.to_numeric(raw['Kualitas Udara'],errors='coerce')
    valid=values.notna() & values.ge(0) & np.isfinite(values.fillna(0).astype(float))
    work['Kualitas Udara']=values.where(valid).astype('Float64')
    reasons=pd.Series('',index=work.index,dtype='str')
    reasons.loc[work['Kode wilayah'].isna()]+='Wilayah tidak cocok dengan master BO; '
    reasons.loc[work.Tanggal.isna()]+='Tanggal tidak valid; '
    reasons.loc[~valid]+='Nilai udara kosong/tidak valid; '
    duplicate=work['Kode wilayah'].notna() & work.Tanggal.notna() & work.duplicated(['Kode wilayah','Tanggal'],keep=False)
    reasons.loc[duplicate]+='Wilayah dan tanggal ganda; tidak dipakai untuk pencocokan; '
    issues=raw.loc[reasons.ne(''),AIR_COLUMNS].copy()
    issues['Masalah']=reasons.loc[reasons.ne('')].str.rstrip('; ')
    daily=work.loc[work['Kode wilayah'].notna() & work.Tanggal.notna() & ~duplicate].reset_index(drop=True)
    metadata=dict(meta or {})
    metadata.update({'rows':len(raw),'valid_values':int(daily['Kualitas Udara'].notna().sum()),
        'regions':int(daily['Kode wilayah'].nunique()),'start':str(daily.Tanggal.min()),'end':str(daily.Tanggal.max())})
    return AirImport(raw,daily,issues.reset_index(drop=True),metadata)

def read_air(content,filename,master):
    meta={'file':filename,'sha256':hashlib.sha256(content).hexdigest(),'sheet':'CSV','header':1,'notes':[]}
    if filename.lower().endswith('.csv'):
        raw=pd.read_csv(BytesIO(content),keep_default_na=False)
    else:
        book=pd.ExcelFile(BytesIO(content),engine='openpyxl')
        raw=None
        name=book.sheet_names[0]
        preview=pd.read_excel(book,sheet_name=name,header=None,nrows=10,keep_default_na=False)
        for index,row in preview.iterrows():
            if set(map(norm,AIR_COLUMNS)).issubset({norm(v) for v in row}):
                raw=pd.read_excel(book,sheet_name=name,header=int(index),keep_default_na=False)
                meta.update({'sheet':name,'header':int(index)+1})
                break
        if raw is None:
            raise ValueError('Sheet pertama harus memuat kolom Kabupaten/Kota, Tanggal, dan Kualitas Udara. Sheet lain tidak digunakan.')
    raw.columns=[next((canonical for canonical in AIR_COLUMNS if norm(canonical)==norm(c)),str(c).strip()) for c in raw.columns]
    return prepare_air(raw,master,meta)

AIR_DETAILS=['AQI 8 hari rata-rata','Hari AQI >50','Hari udara tersedia']

AQI_CATEGORIES=[('Good',50,0),('Moderate',100,25),('Unhealthy for sensitive groups',150,50),('Unhealthy',200,75),('Very Unhealthy / Hazardous',float('inf'),100)]

def aqi_severity(values):
    numeric=pd.to_numeric(values,errors='coerce')
    result=pd.Series(float('nan'),index=values.index,dtype=float)
    valid=numeric.notna() & numeric.ge(0) & np.isfinite(numeric)
    for _,upper,score in reversed(AQI_CATEGORIES):
        result.loc[valid & numeric.le(upper)]=score
    return result

def attach_air(events,daily=None):
    # Eight calendar days: H+0 through H+7, including the disaster date.
    out=events.drop(columns=[AIR_METRIC,'Status udara','AQI 7 hari rata-rata']+AIR_DETAILS,errors='ignore').copy().reset_index(drop=True)
    out['Tanggal']=out.Tanggal.dt.normalize()
    applicable=out['Bencana'].eq('Karhutla') if 'Bencana' in out else pd.Series(False,index=out.index)
    if daily is None or daily.empty:
        out[AIR_METRIC]=float('nan')
        out['AQI 8 hari rata-rata']=float('nan')
        out['Hari AQI >50']=float('nan')
        out['Hari udara tersedia']=0
    else:
        lookup=daily[['Kode wilayah','Tanggal','Kualitas Udara']].copy()
        lookup['Tanggal']=lookup.Tanggal.dt.normalize()
        if lookup.duplicated(['Kode wilayah','Tanggal']).any():
            raise ValueError('Data udara ganda untuk wilayah dan tanggal yang sama.')
        window=out.loc[applicable,['Kode wilayah','Tanggal']].copy()
        window['_event']=window.index
        window=window.loc[window.index.repeat(8)].reset_index(drop=True)
        window['Tanggal']+=pd.to_timedelta(np.tile(np.arange(0,8),int(applicable.sum())),unit='D')
        window=window.merge(lookup,on=['Kode wilayah','Tanggal'],how='left',validate='many_to_one',sort=False)
        window['_severity']=aqi_severity(window['Kualitas Udara'])
        window['_above50']=window['Kualitas Udara'].gt(50).fillna(False).astype(int)
        stats=window.groupby('_event').agg(available=('_severity','count'),aqi=('Kualitas Udara','mean'),severity=('_severity','mean'),above50=('_above50','sum')).reindex(range(len(out)))
        full=stats.available.eq(8)
        out[AIR_METRIC]=stats.severity.where(full).astype(float)
        out['AQI 8 hari rata-rata']=stats.aqi.where(full).astype(float)
        out['Hari AQI >50']=stats.above50.where(full).astype(float)
        out['Hari udara tersedia']=stats.available.fillna(0).astype(int)
    out['Status udara']=out['Hari udara tersedia'].map(lambda n:'Lengkap 8/8 hari (H+0–H+7)' if n==8 else f'Belum lengkap {n}/8 hari (H+0–H+7)')
    out.loc[~applicable,'Status udara']='Tidak berlaku: bukan Karhutla'
    return out
