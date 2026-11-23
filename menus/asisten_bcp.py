"""Asisten BCP menu: unchanged local question parsing and clarification."""
import re
import pandas as pd
import streamlit as st
from data_engine import AIR_METRIC,IMPACTS,csv_bytes,bcp_events
from ui_components import display_table


HAZARD_ALIASES = {
    'Banjir': ['banjir'], 'Cuaca ekstrem': ['cuaca ekstrem', 'cuaca ekstrim', 'puting beliung'],
    'Karhutla': ['kebakaran hutan dan lahan', 'karhutla'],
    'Tanah longsor': ['tanah longsor', 'longsor'],
    'Gempa bumi': ['gempa bumi', 'gempabumi', 'gempa'],
    'Gelombang pasang dan abrasi': ['gelombang pasang dan abrasi', 'gelombang pasang', 'abrasi'],
    'Erupsi gunung api': ['erupsi gunung api', 'gunung meletus', 'erupsi'], 'Tsunami': ['tsunami'],
}

METRIC_ALIASES = {
    AIR_METRIC: ['kualitas udara', 'dampak udara', 'aqi'],
    'Meninggal': ['korban meninggal dunia', 'meninggal dunia', 'meninggal', 'tewas', 'kematian'],
    'Hilang': ['hilang'], 'Terluka': ['luka luka', 'terluka', 'luka', 'cedera'],
    'Rumah Rusak': ['rumah yang rusak', 'rumah rusak'], 'Rumah Terendam': ['rumah yang terendam', 'rumah terendam'],
    'Fasum Rusak': ['fasilitas umum yang rusak', 'fasilitas umum rusak', 'fasum rusak'],
}

class ClarificationNeeded(ValueError):
    def __init__(self, prompt, options):
        super().__init__(prompt)
        self.options=options

def clarify_question(question):
    """Return explicit alternatives; never silently choose a meaning for the user."""
    text=normalize(re.sub(r'(\d{4})\s*[-–—]\s*(\d{4})',r'\1 sampai \2',question))
    # The ordered patterns keep specific ambiguous phrases ahead of generic ones.
    rules=[
        (r'\bkorban jiwa\b','Apa yang dimaksud dengan korban jiwa?',[
            ('Korban meninggal saja','meninggal'),
            ('Rincian meninggal, hilang, dan terluka','meninggal dan hilang dan terluka')]),
        (r'\brumah (?:yang )?terdampak\b','Dampak terhadap rumah yang ingin dihitung?',[
            ('Rumah rusak','rumah rusak'),('Rumah terendam','rumah terendam'),
            ('Rincian keduanya','rumah rusak dan rumah terendam')]),
        (r'\bkerusakan(?: infrastruktur)?\b','Indikator kerusakan yang dimaksud?',[
            ('Rumah rusak','rumah rusak'),('Fasilitas umum rusak','fasum rusak'),
            ('Rincian keduanya','rumah rusak dan fasum rusak')]),
        (r'\b(?:korban terdampak|orang terdampak|warga terdampak|penduduk terdampak|pengungsi)\b','Data ini tidak menyediakan jumlah unik warga terdampak atau pengungsi. Ingin melihat indikator yang tersedia?',[
            ('Korban meninggal','meninggal'),('Korban terluka','terluka'),
            ('Rincian meninggal, hilang, dan terluka','meninggal dan hilang dan terluka')]),
        (r'\bkorban\b(?!\s+(?:meninggal|hilang|terluka|luka|tewas|cedera))','Jenis korban yang ingin dihitung?',[
            ('Korban meninggal','meninggal'),('Korban hilang','hilang'),('Korban terluka','terluka'),
            ('Rincian ketiganya','meninggal dan hilang dan terluka')]),
        (r'\bdampak\b','Dampak apa yang ingin ditampilkan?',[
            ('Dampak manusia','meninggal dan hilang dan terluka'),
            ('Dampak bangunan','rumah rusak dan rumah terendam dan fasum rusak'),
            ('Rincian enam indikator','meninggal dan hilang dan terluka dan rumah rusak dan rumah terendam dan fasum rusak')]),
    ]
    for pattern,prompt,choices in rules:
        if re.search(pattern,text):
            raise ClarificationNeeded(prompt,{label:re.sub(pattern,replacement,text) for label,replacement in choices})
    if re.search(r'\bkebakaran\b',text) and not re.search(r'\bkebakaran hutan dan lahan\b',text):
        raise ClarificationNeeded('Kategori yang tersedia adalah kebakaran hutan dan lahan. Apakah itu yang dimaksud?',
            {'Ya, kebakaran hutan dan lahan':re.sub(r'\bkebakaran\b','karhutla',text)})

def normalize(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', str(text).lower())).strip()

def extract(text, aliases):
    found=[]
    for canonical, names in aliases.items():
        matched=False
        for name in sorted(names, key=len, reverse=True):
            pattern=r'\b'+re.escape(normalize(name))+r'\b'
            if re.search(pattern,text):
                matched=True
                text=re.sub(pattern,' ',text)
        if matched: found.append(canonical)
    return found, text

def parse_question(question, master, default_scope='Wilayah BO terdaftar'):
    if len(question)>1000:
        raise ValueError('Pertanyaan terlalu panjang. Tanyakan satu jumlah kejadian atau dampak dalam satu kalimat.')
    text=normalize(question)
    if re.search(r'\bkekeringan\b',text):
        raise ValueError('Kategori Kekeringan tidak termasuk cakupan dashboard BCP. Pilih salah satu dari 8 kategori bencana yang digunakan.')
    if not text:
        raise ValueError('Tuliskan pertanyaan terlebih dahulu.')
    if re.search(r'\b(tidak|bukan|kecuali|tanpa|selain)\b',text):
        raise ValueError('Pengecualian atau negasi belum didukung. Sebutkan langsung indikator dan bencana yang ingin dihitung.')
    clarify_question(question)
    # Refuse unimplemented qualifiers instead of silently returning a different statistic.
    blocked=r'\b(rata rata|persen|persentase|skor|risiko|skenario|tertinggi|terbanyak|terendah|bandingkan|per tahun|per bulan|januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|kemarin|sekarang|tahun ini|tahun lalu|kecamatan|kabupaten semarang)\b'
    if re.search(blocked,text):
        raise ValueError('Versi ini menghitung jumlah kejadian dan total dampak, dengan filter BO, regional, bencana, dan tahun. Untuk bulan/tanggal khusus, perbandingan, atau penilaian risiko, gunakan menu analisis. Contoh: "Berapa kejadian banjir di Semarang tahun 2026?"')
    scope=default_scope
    if re.search(r'\b(seluruh dataset|semua data|seluruh data|nasional|indonesia)\b',text):
        scope='Seluruh dataset unggahan'
        text=re.sub(r'\b(seluruh dataset|semua data|seluruh data|nasional|indonesia)\b',' ',text)
    years=sorted(set(int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b',text)))
    if len(years)>2: raise ValueError('Gunakan satu tahun atau satu rentang, misalnya 2024–2026.')
    text=re.sub(r'\b(?:19|20)\d{2}\b',' ',text)
    if len(years)==2 and not re.search(r'(?:\d{4}\s*[-–—]\s*\d{4}|\bsampai\b|\bhingga\b|\bsd\b)',question.lower()):
        raise ValueError('Untuk rentang tahun, tulis misalnya "2024 sampai 2026".')
    regional=re.findall(r'\bregional\s*([123])\b',text)
    if len(set(regional))>1: raise ValueError('Tanyakan satu regional per pertanyaan.')
    text=re.sub(r'\bregional\s*[123]\b',' ',text)
    bos,text=extract(text,{name:[name] for name in master.BO})
    if len(bos)>1: raise ValueError('Tanyakan satu BO per pertanyaan, atau gunakan satu regional.')
    hazards,text=extract(text,HAZARD_ALIASES)
    if len(hazards)>1: raise ValueError('Tanyakan satu jenis bencana per pertanyaan.')
    metrics,text=extract(text,METRIC_ALIASES)
    filler={'berapa','berapakah','jumlah','jumlahnya','banyak','banyaknya','total','kejadian','bencana','di','pada','selama','tahun','dari','sampai','hingga','sd','dan','atau','akibat','karena','untuk','bo','business','operation','wilayah','kota','korban','orang','jiwa','unit','yang','ada','terjadi','tercatat','terkena','dampak','tolong','tampilkan','hitung','hitungkan','jelaskan','data','semua','seluruh','tersebut','berapa banyak'}
    unknown=set(text.split())-filler
    if unknown:
        raise ValueError('Bagian pertanyaan belum dikenali: '+', '.join(sorted(unknown))+'. Gunakan nama BO, regional, jenis bencana, indikator dampak, dan tahun secara lengkap.')
    if not metrics and not hazards and not any(w in normalize(question).split() for w in ['kejadian','bencana']):
        raise ValueError('Sebutkan yang ingin dihitung: kejadian, meninggal, hilang, terluka, rumah rusak, rumah terendam, atau fasum rusak.')
    region='Regional '+regional[0] if regional else None
    if bos and region and master.loc[master.BO.eq(bos[0]),'Regional'].iloc[0]!=region:
        raise ValueError('BO dan regional dalam pertanyaan tidak cocok. Periksa pilihan wilayah.')
    return {'scope':scope,'bo':bos[0] if bos else None,'region':region,'hazard':hazards[0] if hazards else None,'metrics':metrics,'years':years}

def answer_question(question, events, master, start, end, scope):
    query=parse_question(question,master,scope)
    start,end=pd.Timestamp(start),pd.Timestamp(end)
    years=query['years']
    requested_start=pd.Timestamp(year=years[0],month=1,day=1) if years else start
    requested_end=pd.Timestamp(year=years[-1],month=12,day=31) if years else end
    lo,hi=max(start,requested_start),min(end,requested_end)
    if lo>hi: raise ValueError('Tahun yang diminta berada di luar periode dataset aktif. Unggah dan aktifkan data untuk tahun tersebut terlebih dahulu.')
    data=bcp_events(events[events.Tanggal.between(lo,hi)])
    selected=master
    if query['region']: selected=selected[selected.Regional.eq(query['region'])]
    if query['bo']: selected=selected[selected.BO.eq(query['bo'])]
    if query['bo'] and selected['ID Kabupaten'].fillna('').eq('').any():
        raise ValueError('BO ini belum cocok dengan wilayah BNPB. Periksa kabupaten/kota dan provinsi di Profil BO, lalu unggah data BNPB yang memuat wilayah tersebut.')
    if query['bo'] or query['region'] or query['scope'] in {'Wilayah 12 BO','Wilayah BO terdaftar'}:
        data=data[data['Kode wilayah'].isin(selected['ID Kabupaten'])]
        area=query['bo'] or query['region'] or f'{len(master)} wilayah BO'
        if query['bo']: area+=' ('+selected['Kabupaten/Kota'].iloc[0]+')'
    else: area='Seluruh wilayah dalam dataset unggahan (cakupan nasional tidak diasumsikan lengkap)'
    if query['hazard']: data=data[data.Bencana.eq(query['hazard'])]
    context=f"**Wilayah:** {area}  \n**Bencana:** {query['hazard'] or 'Semua jenis'}  \n**Periode yang dihitung:** {lo:%d/%m/%Y}–{hi:%d/%m/%Y}"
    lines=[context,'']
    if years and (lo>requested_start or hi<requested_end):
        lines.append('**Cakupan tahun parsial:** jawaban hanya memakai bagian periode yang tersedia pada dataset aktif.\n')
    lines.append(f"**Jumlah kejadian: {len(data):,}.**")
    if data.empty: lines.append('Tidak ditemukan catatan yang cocok; ini bukan bukti bahwa tidak ada bencana di dunia nyata.')
    for metric in query['metrics']:
        if metric==AIR_METRIC:
            fire_data=data[data.Bencana.eq('Karhutla')]
            if fire_data.empty:
                lines.append('Dampak udara hanya berlaku untuk Karhutla; tidak digunakan untuk bencana lain.')
                continue
            values=fire_data[AIR_METRIC].dropna() if AIR_METRIC in fire_data else pd.Series(dtype=float)
            lines.append('**Indeks dampak udara khusus Karhutla rata-rata H+0–H+7 (0–100): '+(f'{values.mean():.2f}' if len(values) else 'tidak tersedia')+f'.** Cocok pada {len(values)}/{len(fire_data)} catatan Karhutla. Ini rata-rata nilai kategori harian; Good = 0. Bukan AQI mentah, jumlah korban, atau konsentrasi PM2.5.')
            continue
        unit='jiwa' if metric in IMPACTS[:3] else 'unit'
        unknown=int(data[metric].isna().sum())
        valid=data[metric].dropna()
        if len(data) and valid.empty:
            lines.append(f'**{metric}: tidak tersedia.** Seluruh nilai pada catatan yang cocok tidak valid/tidak tersedia.')
        else:
            total=int(valid.sum())
            label='Subtotal tercatat' if unknown else 'Total'
            lines.append(f'**{label} {metric.lower()}: {total:,} {unit}.**'+(f' {unknown} dari {len(data)} catatan belum tersedia; total lengkap belum dapat ditentukan.' if unknown else ''))
    if len(query['metrics'])>1:
        lines.append('Indikator ditampilkan terpisah, tidak dijumlahkan menjadi total korban atau bangunan unik karena data tidak memastikan tidak ada tumpang tindih.')
    lines.append('\nJumlah kejadian mengikuti baris yang diterima saat import. Dampak adalah dampak masyarakat di kabupaten/kota, bukan bukti dampak langsung pada kantor BO.')
    if query['metrics']: lines.append('Sel impact kosong pada kolom yang tersedia dihitung 0 sesuai aturan import; nilai tidak valid tetap dianggap belum tersedia.')
    columns=[c for c in ['Baris sumber','Tanggal','Kabupaten','Provinsi','Bencana']+IMPACTS+[AIR_METRIC] if c in data]
    return '\n\n'.join(lines),data[columns].sort_values('Tanggal'),query

def render_assistant(active,master):
    st.info('Asisten tanya jawab lokal berbasis aturan, tanpa model AI generatif/API. Jawaban dihitung langsung dari dataset aktif. Setiap pertanyaan berdiri sendiri.')
    scope=st.radio('Cakupan jika pertanyaan tidak menyebut BO atau regional',['Wilayah BO terdaftar','Seluruh dataset unggahan'],horizontal=True,key='bcp_assistant_scope')
    st.caption('Contoh: Berapa kejadian banjir di Semarang? · Berapa jumlah korban meninggal akibat gempa bumi selama 2026? · Berapa rumah rusak akibat banjir di Regional 2 tahun 2024 sampai 2026?')
    with st.expander('Contoh pertanyaan dan pilihan klarifikasi'):
        st.markdown('''- **Jumlah kejadian:** Berapa banjir di Semarang tahun 2026?
- **Korban jiwa:** Berapa korban jiwa akibat gempa bumi tahun 2026? → pilih meninggal saja atau rincian korban.
- **Rumah terdampak:** Berapa rumah terdampak banjir di Medan? → pilih rusak, terendam, atau rincian keduanya.
- **Kerusakan:** Berapa kerusakan akibat banjir di Regional 2? → pilih rumah atau fasilitas umum.
- **Dampak:** Tampilkan dampak banjir di Jakarta. → pilih dampak manusia, bangunan, atau enam indikator.
- **Beberapa indikator:** Berapa meninggal dan terluka akibat banjir tahun 2024 sampai 2026?

Angka warga terdampak/pengungsi, kerugian rupiah, perbandingan, skor, dan filter bulan belum didukung. Pertanyaan tersebut tidak diubah menjadi angka lain tanpa penjelasan.''')
    token=(active.get('activated'),active.get('start'),active.get('end'))
    if st.session_state.get('bcp_assistant_token')!=token:
        st.session_state.bcp_assistant_token=token
        st.session_state.pop('bcp_assistant_answer',None)
        st.session_state.pop('bcp_assistant_pending',None)
    pending=st.session_state.get('bcp_assistant_pending')
    if pending and pending['scope']!=scope:
        st.session_state.pop('bcp_assistant_pending',None)
        st.info('Cakupan berubah. Kirim ulang pertanyaan untuk memakai cakupan yang baru.')
    with st.form('bcp_assistant_form'):
        question=st.text_input('Pertanyaan tentang data',max_chars=1000,placeholder='Berapa kejadian banjir di Semarang tahun 2026?')
        submitted=st.form_submit_button('Tanyakan',type='primary')
    def process(original,resolved,chosen_scope,history):
        try:
            result=answer_question(resolved,active['result'].events,master,active['start'],active['end'],chosen_scope)
            display=original
            if history: display+='\n\nPilihan klarifikasi: '+' → '.join(history)
            st.session_state.bcp_assistant_answer=(display,*result)
            st.session_state.pop('bcp_assistant_pending',None)
        except ClarificationNeeded as error:
            st.session_state.bcp_assistant_pending={'original':original,'prompt':str(error),'options':error.options,'scope':chosen_scope,'history':history}
        except ValueError as error:
            st.session_state.pop('bcp_assistant_pending',None)
            st.warning(str(error))
    if submitted:
        st.session_state.pop('bcp_assistant_answer',None)
        st.session_state.pop('bcp_assistant_pending',None)
        process(question,question,scope,[])
    pending=st.session_state.get('bcp_assistant_pending')
    if pending:
        st.write('Pertanyaan: '+pending['original'])
        st.info(pending['prompt'])
        # A choice requires a deliberate submit; the first option is never assumed.
        import hashlib
        identity=hashlib.sha256(str(pending).encode()).hexdigest()[:12]
        with st.form('bcp_clarify_'+identity):
            choice=st.radio('Pilih maksud pertanyaan',list(pending['options']),index=None,key='bcp_choice_'+identity)
            confirmed=st.form_submit_button('Gunakan pilihan')
        if confirmed:
            if choice is None:
                st.warning('Pilih salah satu opsi terlebih dahulu.')
            else:
                process(pending['original'],pending['options'][choice],pending['scope'],pending['history']+[choice])
                # Re-render if another phrase needs clarification. Errors remain visible.
                if st.session_state.get('bcp_assistant_pending') or st.session_state.get('bcp_assistant_answer'):
                    st.rerun()
        if st.button('Batalkan klarifikasi'):
            st.session_state.pop('bcp_assistant_pending',None)
            st.rerun()
    saved=st.session_state.get('bcp_assistant_answer')
    if saved:
        question,answer,evidence,query=saved
        with st.chat_message('user'): st.write(question)
        with st.chat_message('assistant'):
            st.markdown(answer)
            st.caption('Sumber: '+str(active.get('meta',{}).get('file','Dataset aktif')))
            with st.expander(f'Lihat dasar jawaban — {len(evidence):,} catatan'):
                display_table(evidence.head(200),hide_index=True,width='stretch')
                if len(evidence)>200: st.caption('Pratinjau 200 baris pertama. Unduh CSV untuk seluruh hasil.')
                st.download_button('Unduh data dasar jawaban',csv_bytes(evidence),'dasar_jawaban_bcp.csv','text/csv')
