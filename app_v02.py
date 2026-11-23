"""BCP dashboard entry: session setup, navigation and shared page layout."""
from datetime import datetime
from pathlib import Path
import streamlit as st
from data_engine import branches,prepare,prepare_air,attach_air,master_signature,HAZARDS,summary
from ui_components import analysis_context,render_period_control,assistant_view,hero,chart
from menus import profil_bo,import_data,overview,analisis_risiko,top_risk,asisten_bcp


ROOT=Path(__file__).resolve().parent
st.set_page_config(page_title='PT SURYA ARTHA NUSANTARA FINANCE',page_icon='◈',layout='wide')
st.markdown('<style>'+ (ROOT/'style.css').read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)
try:
    active=st.session_state.get('v02_active')
    source_raw=active['result'].raw if active else st.session_state.get('v02_source',(None,None))[0]
    MASTER=branches(source_raw)
except (OSError,ValueError) as exc:
    st.error(str(exc)); st.stop()
MASTER_SIGNATURE=master_signature(MASTER)
PAGES=['Profil BO','Import Data','Overview','Analisis Risiko','Top Risk','Asisten BCP']
LOCKED=PAGES[2:]
st.session_state.setdefault('v02_upload_key',0)
if st.session_state.get('v02_active') and (st.session_state.v02_active.get('impact_policy')!='bcp8-air-v5-hazardweights' or st.session_state.v02_active.get('master_signature')!=MASTER_SIGNATURE):
    active=st.session_state.v02_active
    active['result']=prepare(active['result'].raw,active['start'],active['end'],active['dedup'],master=MASTER)
    air=active.get('air')
    if air is not None:
        air=prepare_air(air.raw,MASTER,air.meta)
        active['air']=air
    active['result'].events=attach_air(active['result'].events,air.daily if air is not None else None)
    active['impact_policy']='bcp8-air-v5-hazardweights'
    active['master_signature']=MASTER_SIGNATURE
    active['activated']=datetime.now().isoformat(timespec='microseconds')
    for key in list(st.session_state):
        if key=='report_file' or key.startswith(('bcp_assistant_answer','bcp_assistant_pending','bcp_assistant_token','drill_')):
            st.session_state.pop(key,None)
ANALYSIS=analysis_context(st.session_state.v02_active,MASTER) if st.session_state.get('v02_active') else None
st.session_state.setdefault('v02_page','Profil BO')
if st.session_state.v02_page not in PAGES or (not st.session_state.get('v02_active') and st.session_state.v02_page in LOCKED):
    st.session_state.v02_page='Profil BO'

def navigate(page): st.session_state.v02_page=page

with st.sidebar:
    st.markdown('<div class="brand">◈ PT SURYA ARTHA NUSANTARA FINANCE </div><div class="brand-sub"> BUSINESS CONTINUITY PLAN <br>ANALYTICS WORKSPACE</div>',unsafe_allow_html=True)
    st.divider()
    st.caption('WORKSPACE')
    for item in PAGES:
        locked=item in LOCKED and not st.session_state.get('v02_active')
        st.button(item,key='nav_'+item,width='stretch',disabled=locked,
                  type='primary' if st.session_state.v02_page==item else 'secondary',
                  on_click=navigate,args=(item,))
    if not st.session_state.get('v02_active'):
        st.caption('Aktifkan data pada Import Data untuk membuka menu analisis.')
    page=st.session_state.v02_page
    st.divider()
    st.caption('DATA & CAKUPAN')
    st.write(f'{len(MASTER)} lokasi operasional')
    active=st.session_state.get('v02_active')
    if active:
        st.caption('● Dataset upload aktif')
        st.caption(f"Analisis: {ANALYSIS['start']:%d/%m/%Y} – {ANALYSIS['end']:%d/%m/%Y}")
        st.caption(f"{len(ANALYSIS['events']):,} baris pada periode analisis")
    else: st.caption('Menunggu upload Excel BNPB')
    st.caption('Tingkat kabupaten/kota\n\nData bencana: sesi browser · profil BO: folder project')

TITLES={
 'Asisten BCP':('Asisten BCP','Tanyakan jumlah kejadian dan dampak pada dataset aktif.'),
 'Profil BO':('Profil BO'),
 'Import Data':('Import Data','Upload, tentukan periode, tinjau data, lalu aktifkan.'),
 'Overview':('Overview','Ringkasan kejadian dan dampak pada wilayah BO.'),
 'Analisis Risiko':('Analisis Risiko','Matrix likelihood, impact, dan risiko dengan skala persentil otomatis.'),
 'Top Risk':('Top Risk','Urutan pasangan BO dan jenis bencana berdasarkan skor likelihood × impact.'),
}
if page=='Profil BO':
    st.title('Profil BO')
    st.caption('Alamat dan wilayah administratif Business Operation.')
elif page in ['Overview','Analisis Risiko','Top Risk'] and ANALYSIS is not None:
    hero(page,TITLES[page][1],st.session_state.get('v02_active'),MASTER)
    render_period_control(st.session_state.v02_active,MASTER,ANALYSIS,page)
else:
    hero(page,TITLES[page][1],st.session_state.get('v02_active'),MASTER)

def waiting():
    st.info(f'Mulai dari data Anda. Master {len(MASTER)} lokasi operasional sudah siap untuk dicocokkan dengan file bencana. Unggah file, tinjau kualitasnya, lalu aktifkan untuk mengisi dashboard.')
    st.button('Mulai import BNPB',type='primary',on_click=navigate,args=('Import Data',))

def filter_events(prefix,bo_fixed=None):
    act=st.session_state.v02_active
    events=ANALYSIS['events']
    master=MASTER
    filtered=events[events['Kode wilayah'].isin(master['ID Kabupaten'])].copy()
    start,end=ANALYSIS['start'],ANALYSIS['end']
    st.caption(f'Periode analisis: {start:%d/%m/%Y}–{end:%d/%m/%Y} · {len(filtered):,} catatan wilayah BO')
    return filtered,master,start,end,HAZARDS

if page=='Import Data':
    MASTER=import_data.render(MASTER)
elif page=='Profil BO':
    profil_bo.render(MASTER)
elif not st.session_state.get('v02_active'):
    waiting()
elif page=='Asisten BCP':
    asisten_bcp.render_assistant(assistant_view(st.session_state.v02_active,ANALYSIS),MASTER)
else:
    pending_bo=MASTER.loc[~MASTER['Pemetaan tersedia'],'BO'].tolist()
    if pending_bo: st.warning('BO belum cocok dengan wilayah BNPB: '+', '.join(pending_bo)+'. Periksa kabupaten/kota dan provinsi; skor risiko ditampilkan N/D sampai terpetakan.')
    prefix='analysis'
    events,master,start,end,hazards=filter_events(prefix)
    sm=summary(events,master)
    if page=='Overview':
        overview.render(events,master,start,end,hazards,chart,sm)
    elif page=='Analisis Risiko':
        analisis_risiko.render(events,master,start,end,chart)
    elif page=='Top Risk':
        top_risk.render(events,master,start,end,chart)

# Floating assistant uses the current browser session and active dataset only.
with st.container(key='bcp_chat_launcher'):
    label='Tutup Asisten' if st.session_state.get('bcp_chat_open') else 'Asisten BCP'
    if st.button(label,icon=':material/chat:',type='primary',width='stretch',key='bcp_chat_toggle'):
        st.session_state.bcp_chat_open=not st.session_state.get('bcp_chat_open',False)
        st.rerun()
if st.session_state.get('bcp_chat_open'):
    with st.container(key='bcp_chat_panel',border=True):
        st.subheader('Asisten BCP')
        st.caption('Status: mode lokal · ChatGPT belum terhubung')
        if not st.session_state.get('v02_active'):
            st.info('Unggah dan aktifkan data BNPB terlebih dahulu untuk menanyakan data.')
        elif page=='Asisten BCP':
            st.info('Asisten sedang terbuka dalam tampilan penuh di halaman ini.')
        else:
            asisten_bcp.render_assistant(assistant_view(st.session_state.v02_active,ANALYSIS),MASTER)

st.markdown('<div class="footer">BCP ATLAS · v0.3 &nbsp; / &nbsp; Sumber kejadian: Excel pengguna &nbsp; / &nbsp; Kabupaten/kota &nbsp; / &nbsp; Memori sesi saja</div>',unsafe_allow_html=True)
