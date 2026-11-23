"""Profil BO menu: location map, profile table and BO registration."""
from urllib.parse import quote
import plotly.express as px
import streamlit as st
from data_engine import FIELDS,add_branch
from ui_components import display_table,selected_chart


def add_bo_form(master):
    saved=st.session_state.pop('v02_bo_saved',None)
    if saved:
        for field in FIELDS: st.session_state.pop('bo_add_'+field,None)
        st.success('Business Operation '+saved+' berhasil ditambahkan dan disimpan.')
    with st.container(key='bo_add_panel'):
        with st.expander('Tambah Business Operation'):
            st.markdown('**Tambahkan lokasi operasional baru**')
            st.caption('Lengkapi profil dan wilayah BO.')
            with st.form('add_business_operation'):
                left,right=st.columns(2,gap='large')
                with left:
                    name=st.text_input('BO',key='bo_add_BO',max_chars=100,placeholder='Contoh: Bandung')
                with right:
                    district=st.text_input('Kecamatan',key='bo_add_Kecamatan',max_chars=150,placeholder='Contoh: Coblong')
                left,right=st.columns(2,gap='large')
                with left:
                    county=st.text_input('Kabupaten/Kota',key='bo_add_Kabupaten/Kota',max_chars=150,
                        placeholder='Contoh: Kota Bandung',
                        help='Bedakan Kota dan Kabupaten, misalnya Kota Bandung atau Kabupaten Bandung. Ikuti nama wilayah pada data BNPB.')
                with right:
                    province=st.text_input('Provinsi',key='bo_add_Provinsi',max_chars=150,placeholder='Contoh: Jawa Barat')
                address=st.text_area('Alamat',key='bo_add_Alamat',max_chars=1000,height=110,
                    placeholder='Nama gedung, jalan, nomor, kelurahan, dan kode pos')
                _,action=st.columns([2,1],gap='large',vertical_alignment='bottom')
                with action:
                    submitted=st.form_submit_button('Simpan Business Operation',type='primary',width='stretch')
            if submitted:
                try:
                    record=add_branch(dict(zip(FIELDS,[name,address,district,county,province])),master)
                    st.session_state.v02_bo_saved=record['BO']
                    st.rerun()
                except (ValueError,OSError) as exc:
                    st.error(str(exc))

def bo_location_map(master):
    master=master.loc[master[['Latitude','Longitude']].notna().all(axis=1)].copy()
    colors={'Regional 1':'#2563EB','Regional 2':'#089981','Regional 3':'#7C3AED','Belum ditetapkan':'#64748b'}
    fig=px.scatter_map(master,lat='Latitude',lon='Longitude',color='Regional',
        color_discrete_map=colors,category_orders={'Regional':list(colors)},
        text='BO',custom_data=['BO','Regional','Kecamatan','Kabupaten/Kota','Alamat'],
        center={'lat':-2.2,'lon':118},zoom=3.3,map_style='open-street-map')
    fig.update_traces(marker=dict(size=19,opacity=1),textposition='top center',textfont=dict(size=14,color='#17365d'),
        hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Kecamatan %{customdata[2]}<br>%{customdata[3]}<br>%{customdata[4]}<br><i>Koordinat perkiraan</i><extra></extra>')
    fig.update_layout(height=520,margin=dict(l=0,r=0,t=0,b=0),
        legend=dict(title=None,orientation='h',y=1.02,x=0,bgcolor='#eef5ff',bordercolor='#d5e4f5',borderwidth=1),
        hoverlabel=dict(bgcolor='#ffffff',font=dict(color='#17365d',size=14)),
        paper_bgcolor='rgba(0,0,0,0)',uirevision='bo-location-map')
    return fig

def render(MASTER):
    map_selection=selected_chart(bo_location_map(MASTER),520,'profile_map')
    if map_selection:
        selected_bo=MASTER[MASTER.BO.eq(map_selection[0])].iloc[0]
        with st.container(border=True):
            st.subheader('Lokasi Pilihan · '+selected_bo.BO)
            st.write(selected_bo.Alamat)
            st.caption(selected_bo['Kecamatan']+' · '+selected_bo['Kabupaten/Kota']+' · '+selected_bo.Regional)
            st.caption('Koordinat perkiraan; belum diverifikasi pada titik gedung.')
    unlocated=MASTER[['Latitude','Longitude']].isna().any(axis=1)
    if unlocated.any(): st.caption(f'{int(unlocated.sum())} BO belum memiliki koordinat; profil tetap masuk tabel dan analisis, tetapi belum ditampilkan sebagai titik peta.')
    st.subheader(f'{len(MASTER)} lokasi Business Operation')
    profile=MASTER[['BO','Alamat','Kecamatan','Kabupaten/Kota','Provinsi']].copy()
    pending=MASTER['Status kecamatan'].eq('Perlu konfirmasi')
    profile.loc[pending,'Kecamatan']=profile.loc[pending,'Kecamatan']+' *'
    display_table(profile,hide_index=True,width='stretch')
    add_bo_form(MASTER)
    if MASTER['BO tambahan'].any():
        with st.expander('Status pencocokan BO tambahan dengan BNPB'):
            display_table(MASTER.loc[MASTER['BO tambahan'],['BO','Kabupaten/Kota','Provinsi','ID Kabupaten','Status pemetaan']],hide_index=True,width='stretch')
    bo=st.selectbox('Pilih Business Operation',MASTER.BO.tolist(),key='profile_selected')
    branch=MASTER[MASTER.BO.eq(bo)].iloc[0]
    with st.container(border=True):
        st.subheader(bo+' · '+branch['Kabupaten/Kota'])
        st.write(branch.Alamat)
        st.write('Kecamatan: '+branch['Kecamatan'])
        st.caption(f"ID Kabupaten: {branch['ID Kabupaten'] or 'Belum terpetakan'}")
        st.link_button('Cari alamat di Google Maps','https://www.google.com/maps/search/?api=1&query='+quote(branch.Alamat))
        st.caption('Tautan pencarian alamat; koordinat gedung belum diverifikasi.')
