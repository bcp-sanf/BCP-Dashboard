"""Top Risk menu: top ten BO-hazard pairs and P80 BO priority screening."""
from math import ceil
import pandas as pd
import plotly.express as px
import streamlit as st
from data_engine import HAZARDS
from ui_components import display_table,selected_chart,source_panel
from menus.analisis_risiko import render_scoring_details


def _p80(values):
    valid=values.dropna()
    return float(valid.quantile(.8,interpolation='linear')) if len(valid) else None

def priority_summary(frame,master):
    """Zero is reserved for no events; missing event scores remain unknown."""
    grid=pd.MultiIndex.from_product([master.BO.tolist(),HAZARDS],names=['BO','Bencana'])
    source=frame.set_index(['BO','Bencana']).reindex(grid)
    counts=source['Catatan'].fillna(0)
    risk=source['Risiko'].astype(float).where(counts.gt(0),0.0)
    unresolved=master.loc[master['ID Kabupaten'].fillna('').eq(''),'BO']
    risk.loc[risk.index.get_level_values('BO').isin(unresolved)]=float('nan')
    t=_p80(risk[risk.gt(0)])
    matrix=risk.unstack('Bencana').reindex(index=master.BO,columns=HAZARDS)
    complete=matrix.notna().all(axis=1)
    totals=matrix.sum(axis=1,min_count=len(HAZARDS))
    high=matrix.gt(t).sum(axis=1) if t is not None else pd.Series(0,index=matrix.index)
    # Unknown cells are excluded from reference BO counts and totals, not imputed.
    count_p80=_p80(high[complete]) if t is not None else None
    k=max(2,ceil(round(count_p80,12))) if count_p80 is not None else None
    s=_p80(totals[complete])
    rows=[]
    for bo in master.BO:
        scores=matrix.loc[bo]
        maximum=float(scores.max()) if scores.notna().any() else None
        missing=int(scores.isna().sum())
        c1=bool(scores.eq(25).any())
        c2=k is not None and int(high.loc[bo])>=k
        c3=s is not None and pd.notna(totals.loc[bo]) and float(totals.loc[bo])>s
        priority=c1 or c2 or c3
        reasons=[]
        if c1: reasons.append('Skor 25: '+', '.join(scores.index[scores.eq(25)]))
        if c2: reasons.append(f'{int(high.loc[bo])} kategori bencana > {_number(t)}')
        if c3: reasons.append(f'Skor kumulatif {_number(totals.loc[bo])} > {_number(s)}')
        if missing: reasons.append(f'{missing} pasangan N/D; kumulatif belum lengkap')
        if priority: status='Prioritas'
        elif missing: status='Perlu tinjau data'
        elif not counts.loc[bo].gt(0).any(): status='Tidak ada catatan'
        else: status='Belum prioritas'
        if not reasons:
            reasons.append('Tidak ada catatan kejadian pada periode aktif' if status=='Tidak ada catatan' else 'Belum memenuhi ketiga kriteria')
        rows.append({'BO':bo,'Status':status,'Skor Tertinggi':maximum,
            'Jumlah Bencana > T':int(high.loc[bo]) if t is not None else None,
            'Skor Kumulatif':float(totals.loc[bo]) if pd.notna(totals.loc[bo]) else None,
            'Alasan':'; '.join(reasons),'_priority':priority,'_missing':missing,
            '_c1':c1,'_c2':c2,'_c3':c3})
    result=pd.DataFrame(rows)
    result=result.sort_values(['_priority','Skor Tertinggi','Jumlah Bencana > T','Skor Kumulatif','BO'],
        ascending=[False,False,False,False,True],na_position='last',kind='stable').reset_index(drop=True)
    return result,{'T':t,'K':k,'S':s,'count_p80':count_p80,
        'positive_pairs':int(risk.gt(0).sum()),'complete_bo':int(complete.sum()),'total_bo':len(master)}

def _number(value):
    return 'N/D' if value is None or pd.isna(value) else f'{value:.4f}'.rstrip('0').rstrip('.').replace('.',',')

def render_priorities(frame,master):
    result,bounds=priority_summary(frame,master)
    with st.container(border=True,key='bo_priority_section'):
        st.subheader('BO Prioritas')
        st.write('BO menjadi prioritas jika memenuhi salah satu kriteria berikut: ')
        st.markdown(f"1. Minimal **skor risiko individu 25**.\n"
            f"2. Minimal **{_number(bounds['K'])} kategori bencana** memiliki skor **> {_number(bounds['T'])}**.\n"
            f"3. **Skor risiko kumulatif > {_number(bounds['S'])}**.")
        a,b,c,d=st.columns(4)
        a.metric('Minimal kategori',_number(bounds['K']))
        b.metric('Threshold risiko',_number(bounds['T']))
        c.metric('Threshold kumulatif',_number(bounds['S']))
        d.metric('BO Prioritas',f"{int(result['_priority'].sum())}/{len(master)}")
        if any(bounds[x] is None for x in ['T','K','S']):
            st.info('Sebagian ambang belum dapat dihitung. Kriteria yang datanya tersedia tetap digunakan; skor individu 25 tetap memicu prioritas.')
        if result['_missing'].gt(0).any():
            st.warning('Ada skor N/D. Kumulatif BO terkait tidak dihitung dan BO tersebut dikeluarkan dari pembanding K dan S. Jika skor yang sudah tersedia memenuhi kriteria 1 atau 2, BO tetap prioritas; selain itu perlu tinjau data.')
        columns=['BO','Status','Skor Tertinggi','Jumlah Bencana > T','Skor Kumulatif','Alasan']
        display=result[columns].rename(columns={'Jumlah Bencana > T':f"Jumlah Bencana > {_number(bounds['T'])}"})
        display_table(display,hide_index=True,width='stretch')

def render(events,master,start,end,chart):
    frame=render_scoring_details(events,master,start,end,top=True)
    if frame.empty:
        st.info('Tidak ada jenis bencana pada dataset ini.')
        render_priorities(frame,master)
        return
    ranked=frame.dropna(subset=['Risiko']).sort_values(['Risiko','BO','Bencana'],ascending=[False,True,True]).copy()
    if ranked.empty:
        st.info('Belum ada pasangan BO dan bencana dengan data cukup untuk diperingkat.')
        render_priorities(frame,master)
        return
    ranked.insert(0,'Peringkat',ranked.Risiko.rank(method='dense',ascending=False).astype(int))
    view=ranked.head(10).copy(); view['BO / Bencana']=view.BO+' / '+view.Bencana
    fig=px.bar(view.sort_values('Risiko'),x='Risiko',y='BO / Bencana',orientation='h',color='Risiko',custom_data=['BO','Bencana'],color_continuous_scale='YlOrRd')
    selected=selected_chart(fig,max(320,len(view)*35),'top_risk')
    if selected: source_panel(events,master,'top_risk',bo=selected[0],hazard=selected[1],scores=frame)
    render_priorities(frame,master)
