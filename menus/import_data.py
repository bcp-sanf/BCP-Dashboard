"""Import Data menu: BNPB and air uploads, validation and dataset activation."""
from datetime import datetime
import hashlib
import streamlit as st
from data_engine import branches,read_source,workbook_layout,prepare,csv_bytes,read_air,attach_air,AIR_METRIC,master_signature
from ui_components import display_table,workflow
import pandas as pd


def source_bounds(raw):
    text = raw['Tanggal Kejadian'].astype(str).str.strip()
    iso = text.str.match(r'^\d{4}-\d{2}-\d{2}(?:[ T].*)?$')
    dates = pd.to_datetime(text, format='mixed', dayfirst=True, errors='coerce')
    dates.loc[iso] = pd.to_datetime(text[iso], format='ISO8601', errors='coerce')
    valid = dates.dropna()
    if valid.empty:
        raise ValueError('Tidak ada tanggal valid untuk menentukan periode dataset.')
    return valid.min().date(), valid.max().date()

def load_bnpb_upload(upload):
    content=upload.getvalue(); signature=hashlib.sha256(content).hexdigest()
    if st.session_state.get('v02_layout_hash')!=signature:
        options,names=workbook_layout(content) if upload.name.lower().endswith('.xlsx') else ([{'sheet':'CSV','header':0}],['CSV'])
        st.session_state.v02_layout_hash=signature
        st.session_state.v02_layout=(options,names)
    options,names=st.session_state.v02_layout
    if not options: raise ValueError('Tidak ada tabel detail BNPB yang dikenali. Diperlukan ID Kabupaten, Tanggal Kejadian, Kejadian, Kabupaten, Provinsi.')
    selected=options[0]['sheet']; parser_key=(signature,selected)
    if st.session_state.get('v02_parser_key')!=parser_key:
        raw,meta=read_source(content,upload.name,sheet=selected)
        st.session_state.v02_parser_key=parser_key
        st.session_state.v02_source=(raw,meta)
        detected_start,detected_end=source_bounds(raw)
        st.session_state.v02_import_start=detected_start
        st.session_state.v02_import_end=detected_end
    raw,meta=st.session_state.v02_source
    return raw,meta,signature,parser_key

def render(MASTER):
    workflow(st.session_state.get('v02_active'),MASTER)
    st.info('Gunakan Data Histori Bencana dari Website BNPB: [https://gis.bnpb.go.id/](https://gis.bnpb.go.id/) → Data Bencana')
    st.caption('Analisis BCP menggunakan 8 kategori bencana. Kekeringan otomatis dikeluarkan; file Excel sumber tetap dapat diunggah tanpa diedit.')
    upload=st.file_uploader('Upload Excel BNPB (.xlsx)',type=['xlsx','csv'],max_upload_size=30,help='Ukuran maksimum 30 MB per file.',key='v02_file_'+str(st.session_state.v02_upload_key))
    air_upload=st.file_uploader('Upload kualitas udara harian (.xlsx / .csv)',type=['xlsx','csv'],max_upload_size=30,
        help='Excel hanya memakai sheet pertama. Kolom: Kabupaten/Kota, Tanggal, Kualitas Udara. Nilai lebih tinggi berarti pencemaran lebih buruk.',key='v02_air_file_'+str(st.session_state.v02_upload_key))
    source_ready=False
    if upload:
        try:
            raw,meta,signature,parser_key=load_bnpb_upload(upload)
            MASTER=branches(raw)
            source_ready=True
        except Exception as exc:
            st.error(f'File BNPB belum dapat diproses: {exc}')
    air_result=None
    if air_upload:
        try:
            air_content=air_upload.getvalue()
            air_signature='first-sheet-v1:'+hashlib.sha256(air_content).hexdigest()+'|'+master_signature(MASTER)
            if st.session_state.get('v02_air_signature')!=air_signature:
                st.session_state.v02_air_preview=read_air(air_content,air_upload.name,MASTER)
                st.session_state.v02_air_signature=air_signature
            air_result=st.session_state.v02_air_preview
            st.caption(f"Udara: {air_result.meta['regions']} wilayah · {air_result.meta['valid_values']:,} nilai harian valid · sheet {air_result.meta['sheet']} · semakin tinggi semakin buruk.")
            for note in air_result.meta.get('notes',[]): st.warning(note)
            if air_result.meta.get('parameter'): st.caption(air_result.meta['parameter'])
            with st.expander('Preview kualitas udara (50 baris pertama)'):
                display_table(air_result.raw.head(50),hide_index=True,width='stretch')
            if len(air_result.issues):
                with st.expander('Catatan validasi kualitas udara'):
                    display_table(air_result.issues,hide_index=True,width='stretch')
        except Exception as exc:
            st.error(f'File kualitas udara belum dapat diproses: {exc}')
    else:
        st.info('Unggah BNPB untuk analisis. File kualitas udara hanya diperlukan untuk menilai impact Karhutla; bencana lain tetap dapat dinilai tanpa file udara.')
    if source_ready:
        try:
            # Streamlit removes date-widget keys when leaving this page.
            # Restore the active period for this BNPB file before recreating widgets.
            if 'v02_import_start' not in st.session_state or 'v02_import_end' not in st.session_state:
                detected_start,detected_end=source_bounds(raw)
                current=st.session_state.get('v02_active')
                same_file=current is not None and current['meta'].get('sha256')==signature
                st.session_state.setdefault('v02_import_start',current['start'] if same_file else detected_start)
                st.session_state.setdefault('v02_import_end',current['end'] if same_file else detected_end)
            st.markdown('#### Periode data')
            a,b=st.columns(2)
            start=a.date_input('Awal cakupan dataset',key='v02_import_start')
            end=b.date_input('Tanggal batas data / cutoff',key='v02_import_end')
            st.caption('Periode awal terdeteksi dari tanggal valid dalam file. Anda dapat membatasi cakupan sebelum aktivasi.')
            if start>end: raise ValueError('Tanggal awal harus sebelum atau sama dengan cutoff.')
            with st.expander('Preview data (50 baris pertama)'):
                display_table(raw.head(50),hide_index=True,width='stretch')
            dedup=False
            prepare_key=(parser_key,start,end,dedup,'bcp8-air-v5-hazardweights',master_signature(MASTER))
            if st.session_state.get('v02_prepare_key')!=prepare_key:
                st.session_state.v02_preview=prepare(raw,start,end,dedup,master=MASTER)
                st.session_state.v02_prepare_key=prepare_key
            result=st.session_state.v02_preview
            if len(result.rejected):
                with st.expander('Baris yang dikeluarkan'):
                    display_table(result.rejected,hide_index=True,width='stretch')
                    st.download_button('Unduh baris yang dikeluarkan',csv_bytes(result.rejected),'baris_dikeluarkan.csv','text/csv')
            if len(result.impact_issues):
                st.warning('Ada nilai dampak tidak valid atau kolom impact yang hilang. Kejadiannya tetap digunakan, tetapi dampak bermasalah tetap tidak tersedia.')
                display_table(result.impact_issues,hide_index=True,width='stretch')
            joined=attach_air(result.events,air_result.daily if air_result is not None else None)
            bo_events=joined[joined['Kode wilayah'].isin(MASTER['ID Kabupaten'])]
            fire_events=bo_events[bo_events.Bencana.eq('Karhutla')]
            air_matched=int(fire_events[AIR_METRIC].notna().sum())
            if air_result is not None and len(fire_events):
                st.info(f'Pencocokan udara: {air_matched:,} dari {len(fire_events):,} catatan Karhutla wilayah BO mempunyai nilai dengan data udara lengkap H+0 sampai H+7 pada wilayah yang sama.')
            if air_matched<len(fire_events):
                st.warning('Sebagian kejadian Karhutla belum memiliki data udara lengkap. Impact dan risiko pasangan Karhutla terkait tampil N/D; bencana lainnya tetap dinilai dari indikator BNPB yang berlaku.')
                with st.expander('Kejadian Karhutla tanpa kecocokan udara'):
                    display_table(fire_events.loc[fire_events[AIR_METRIC].isna(),['Tanggal','Kabupaten','Bencana']].head(200),hide_index=True,width='stretch')
            confirmed=st.checkbox('Saya sudah meninjau periode, data BNPB, dan kecocokan udara jika digunakan untuk Karhutla.',key='v02_import_confirmed')
            can_activate=confirmed and len(result.events)>0 and (air_upload is None or air_result is not None)
            if st.button('Gunakan data ini pada dashboard',type='primary',disabled=not can_activate):
                result.events=joined
                st.session_state.v02_active={'result':result,'meta':meta,'air':air_result,'start':start,'end':end,'dedup':dedup,'activated':datetime.now().isoformat(timespec='microseconds'),'impact_policy':'bcp8-air-v5-hazardweights','master_signature':master_signature(MASTER)}
                # Reset data-dependent filters so replacing a file cannot leave stale bounds.
                for k in list(st.session_state):
                    if k.startswith(('ov_','profile_','an_','compare_','explore_','report_')): del st.session_state[k]
                st.session_state.pop('risk_method',None)
                st.session_state.v02_page='Overview'
                st.rerun()
        except Exception as exc:
            st.error(f'File belum dapat diproses: {exc}')
    if st.session_state.get('v02_active'):
        act=st.session_state.v02_active
        st.subheader('Dataset aktif')
        st.write(f"{act['meta']['file']} · {act['meta']['sheet']} · diaktifkan {act['activated']}")
        if act.get('air') is not None:
            st.caption('File aktif: '+act['air'].meta['file'])
        else:
            st.warning('Dataset belum memiliki file udara. Bencana selain Karhutla tetap dinilai; lengkapi file udara untuk menghitung impact Karhutla.')
        st.caption('Upload dan aktivasi berikutnya mengganti dataset aktif, bukan menambahkan baris. Tutup/reset sesi atau restart server untuk mengakhiri data sementara.')
        if st.button('Kosongkan data sesi'):
            for k in list(st.session_state):
                if k.startswith('v02_') and k not in ['v02_page','v02_upload_key']: del st.session_state[k]
                elif k.startswith(('ov_','profile_','an_','compare_','explore_','report_','bcp_assistant_','drill_')): del st.session_state[k]
            st.session_state.pop('risk_method',None)
            st.session_state.v02_upload_key+=1
            st.rerun()
    return MASTER
