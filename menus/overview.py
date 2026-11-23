"""Overview menu: summary KPI, composition, monthly trend and regional view."""
from html import escape
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from data_engine import IMPACTS,HAZARDS,summary,heatmap,monthly,impact_total
from ui_components import COLORS,fmt,selected_chart,selected_pie,source_panel,heatmap_targets


def brief(events, master):
    if events.empty:
        st.info('Tidak ada catatan untuk kombinasi filter ini. Ubah periode, BO, atau jenis bencana untuk memperluas analisis.')
        return
    sm = summary(events, master).sort_values('Catatan kejadian', ascending=False)
    top = sm.iloc[0]
    hazard = events.Bencana.value_counts()
    completeness = events[IMPACTS].notna().to_numpy().mean() * 100
    items = [
        ('WILAYAH TERBANYAK', str(top.BO), f"{int(top['Catatan kejadian']):,} catatan · {top['Catatan kejadian']/len(events):.1%} dari filter"),
        ('BENCANA DOMINAN', str(hazard.index[0]), f'{int(hazard.iloc[0]):,} catatan · {hazard.iloc[0]/len(events):.1%} dari filter'),
        ('KELENGKAPAN DAMPAK', f'{completeness:.1f}%', 'Sel terisi pada enam kolom dampak'),
    ]
    html = ''.join(f'<div class="insight"><small>{escape(a)}</small><h3>{escape(b)}</h3><p>{escape(c)}</p></div>' for a,b,c in items)
    st.markdown('<div class="insights">'+html+'</div>', unsafe_allow_html=True)

def regional_view(events, master, chart):
    data=summary(events,master)
    data['Regional']=data['BO'].map(master.set_index('BO')['Regional'])
    regions=['Regional 1','Regional 2','Regional 3']+[r for r in data.Regional.dropna().unique() if r not in ['Regional 1','Regional 2','Regional 3']]
    colors={'Regional 1':'#2563EB','Regional 2':'#089981','Regional 3':'#7C3AED','Belum ditetapkan':'#64748b'}
    for column,region in zip(st.columns(len(regions)),regions):
        subset=data[data.Regional.eq(region)]
        column.metric(region,f"{int(subset['Catatan kejadian'].sum()):,} kejadian")
        column.caption(f'{len(subset)} BO')
    data['posisi']=data.groupby('Regional').cumcount()
    data['x']=data['posisi'].mod(2)
    data['y']=1-data['posisi'].floordiv(2)
    data['label']=data['BO']+'<br>'+data['Catatan kejadian'].astype(str)+' kejadian'
    fig=px.scatter(data,x='x',y='y',facet_col='Regional',
        category_orders={'Regional':regions},color='Regional',color_discrete_map=colors,
        size='Catatan kejadian',size_max=75,text='label',
        custom_data=['BO','Regional','Catatan kejadian','Kabupaten/Kota'])
    fig.update_traces(marker=dict(sizemin=9,line=dict(width=2,color='white'),opacity=.85),
        textposition='bottom center',textfont=dict(size=15,color='#142d50'),
        hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[3]}<br>%{customdata[2]} kejadian<extra></extra>')
    fig.update_xaxes(visible=False,range=[-.6,1.6],fixedrange=True)
    rows=max(2,int(data.groupby('Regional').size().max()+1)//2)
    fig.update_yaxes(visible=False,range=[1-(rows-1)-.65,1.6],fixedrange=True)
    fig.for_each_annotation(lambda a:a.update(text=a.text.split('=')[-1]))
    fig.update_layout(showlegend=False,margin=dict(l=10,r=10,t=40,b=15),
        plot_bgcolor='#f5f7fa',paper_bgcolor='rgba(0,0,0,0)')
    selected=selected_chart(fig,max(390,rows*95+150),'regional')
    if selected: source_panel(events,master,'regional',bo=selected[0])
    st.caption('Kelompok mengikuti pembagian regional operasional. Ukuran gelembung mengikuti jumlah kejadian; BO dengan 0 kejadian tetap ditampilkan sebagai titik kecil. Arahkan kursor untuk melihat detail.')

def impact_cards(events,metrics=IMPACTS[:3]):
    with st.container(key="impact_summary"):
        for column,metric in zip(st.columns(len(metrics)),metrics):
            value,known,total=impact_total(events,metric)
            column.metric(metric+' tercatat',fmt(value))
            column.caption(f'{known:,}/{total:,} baris berisi nilai · '+('jiwa' if metric in IMPACTS[:3] else 'unit'))

def render(events,master,start,end,hazards,chart,sm):
    overview_kpis=[
        ('Wilayah BO yang terdampak',f"{int(sm['Catatan kejadian'].gt(0).sum())}/{len(master)}",''),
        ('Jumlah Kejadian',fmt(len(events)),''),
        ('Jenis Bencana',f"{events.loc[events.Bencana.isin(HAZARDS),'Bencana'].nunique()}/{len(HAZARDS)}",'*berdasarkan kategori bencana BNPB'),
    ]
    for column,(label,value,note),accent in zip(st.columns(3),overview_kpis,['#3875f6','#12b8a6','#8b6de9']):
        column.markdown(
            f'<div class="overview-kpi" style="border-top-color:{accent}">'
            f'<div class="overview-kpi-label">{label}</div>'
            f'<div class="overview-kpi-value">{value}</div>'
            f'<div class="overview-kpi-note">{note}</div></div>',
            unsafe_allow_html=True,
        )
    brief(events,master)
    overview_chart_height=max(520,115+len(master)*34)
    left,right=st.columns(2)
    with left,st.container(border=True,key='overview_bo_card'):
        st.subheader('Komposisi Wilayah')
        fig=px.bar(sm.sort_values('Catatan kejadian'),x='Catatan kejadian',y='BO',orientation='h',text='Catatan kejadian',hover_data=['Kabupaten/Kota'],custom_data=['BO'],color_discrete_sequence=['#2563eb'])
        selected=selected_chart(fig,overview_chart_height,'overview_bo')
        if selected: source_panel(events,master,'overview_bo',bo=selected[0],summary_by='bencana')
    with right,st.container(border=True,key='overview_hazard_card'):
        st.subheader('Komposisi Bencana')
        if len(events):
            counts=events.Bencana.value_counts().rename_axis('Bencana').reset_index(name='Catatan kejadian')
            selected=selected_pie(counts,COLORS,height=overview_chart_height)
            if selected: source_panel(events,master,'overview_hazard',hazard=selected[0],summary_by='bo')
        else: st.info('Belum ada catatan pada filter ini.')
    st.subheader('Dampak terhadap masyarakat di wilayah BO')
    impact_cards(events)
    with st.container(border=True):
        st.subheader('Matriks frekuensi BO × bencana')
        matrix=heatmap(events,master,hazards)
        fig=go.Figure(go.Heatmap(z=matrix.values,x=matrix.columns,y=matrix.index,text=matrix.values,texttemplate='%{text}',textfont=dict(size=14),colorscale=[[0,'#eef3f5'],[.25,'#b9dfd8'],[1,'#087f8c']],zmin=0,zmax=max(1,int(matrix.to_numpy().max())),xgap=4,ygap=4,showscale=False,hovertemplate='%{y}<br>%{x}: %{z} catatan<extra></extra>'))
        fig.update_yaxes(autorange='reversed'); fig.update_xaxes(tickangle=-25)
        selected=selected_chart(heatmap_targets(fig,master,matrix.columns),max(350,len(master)*31+120),'overview_matrix')
        if selected: source_panel(events,master,'overview_matrix',bo=selected[0],hazard=selected[1])
    with st.container(border=True):
        st.subheader('Tren bulanan dalam cakupan')
        trend=monthly(events,start,end)
        fig=px.line(trend,x='Bulan',y='Catatan kejadian',markers=True,custom_data=['Bulan'],color_discrete_sequence=['#2563eb'])
        selected=selected_chart(fig,270,'overview_month')
        if selected: source_panel(events,master,'overview_month',month=selected[0])
    with st.expander('Sebaran Kejadian per Regional',expanded=True):
        regional_view(events,master,chart)
