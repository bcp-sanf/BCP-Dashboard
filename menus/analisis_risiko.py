"""Analisis Risiko menu and the unchanged likelihood/impact calculation."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_engine import AIR_METRIC,attach_air,HAZARDS,IMPACTS,match_branches,csv_bytes,bcp_events
from ui_components import display_table,selected_chart,source_panel,heatmap_targets,selection_key


WEIGHTS={'Meninggal':.30,'Hilang':.10,'Terluka':.10,'Rumah Rusak':.15,'Rumah Terendam':.15,'Fasum Rusak':.20,AIR_METRIC:0.0}

KARHUTLA_WEIGHTS={'Meninggal':.30,'Hilang':.10,'Terluka':.10,'Rumah Rusak':.10,'Rumah Terendam':0.0,'Fasum Rusak':.10,AIR_METRIC:.30}

IMPACT_METRICS=list(WEIGHTS)

def weights_for(hazard):
    return KARHUTLA_WEIGHTS if hazard=='Karhutla' else WEIGHTS

def quantile_scores(values,quantiles,offset):
    valid=values.dropna().astype(float)
    bounds=valid.quantile(quantiles,interpolation='linear').tolist() if len(valid) else []
    scores=pd.Series(float('nan'),index=values.index,dtype=float)
    if len(valid): scores.loc[valid.index]=valid.map(lambda x:offset+sum(x>b for b in bounds))
    return scores,bounds

def normalize(values):
    scores=pd.Series(float('nan'),index=values.index,dtype=float)
    scores.loc[values.eq(0)]=0
    positive=values[values.gt(0)].astype(float)
    if len(positive): scores.loc[positive.index]=100*positive.rank(method='average',pct=True)
    return scores

def calculate(events,master,start,end):
    if pd.Timestamp(start)>pd.Timestamp(end): raise ValueError('Periode tidak valid')
    selected=bcp_events(events[events.Tanggal.between(pd.Timestamp(start),pd.Timestamp(end))])
    if AIR_METRIC not in selected: selected=attach_air(selected)
    matched=match_branches(selected,master)
    rows=[]
    for _,bo in master.iterrows():
        for hazard in sorted(selected.Bencana.unique()):
            subset=matched[matched.bo_id.eq(bo.bo_id)&matched.Bencana.eq(hazard)]
            n=len(subset)
            row={'BO':bo.BO,'Bencana':hazard,'Catatan':n,'Pemetaan tersedia':bool(str(bo['ID Kabupaten']).strip())}
            for metric in IMPACT_METRICS:
                known=int(subset[metric].notna().sum())
                if metric!=AIR_METRIC:
                    row[metric+' jumlah']=float(subset[metric].sum()) if known==n else float('nan')
                row[metric+' terisi']=known
                row[metric+' rata-rata']=float(subset[metric].mean()) if n and known==n else float('nan')
            for extra in ['AQI 8 hari rata-rata','Hari AQI >50']:
                row[extra]=float(subset[extra].mean()) if n and extra in subset and subset[extra].notna().all() else float('nan')
            rows.append(row)
    columns=['BO','Bencana','Catatan','Pemetaan tersedia']+[c for m in IMPACT_METRICS for c in ([m+' terisi',m+' rata-rata']+([m+' jumlah'] if m!=AIR_METRIC else []))]
    frame=pd.DataFrame(rows,columns=columns+['AQI 8 hari rata-rata','Hari AQI >50'])
    frame['Likelihood'],lb=quantile_scores(frame.Catatan.where(frame.Catatan.gt(0)),[.2,.4,.6,.8],1)
    weight_frame=pd.DataFrame([weights_for(h) for h in frame.Bencana],index=frame.index,columns=IMPACT_METRICS)
    known=pd.DataFrame({m:frame[m+' rata-rata'].notna() for m in IMPACT_METRICS},index=frame.index)
    required=weight_frame.gt(0)
    complete=frame.Catatan.gt(0) & (known | ~required).all(axis=1)
    frame['Indikator lengkap']=(known & required).sum(axis=1)
    frame['Indikator diperlukan']=required.sum(axis=1)
    contributions=[]
    for m in IMPACT_METRICS:
        eligible=complete & required[m]
        frame[m+' normalisasi']=(frame[m+' rata-rata'].where(eligible) if m==AIR_METRIC else normalize(frame[m+' rata-rata'].where(eligible)))
        column=m+' kontribusi'
        frame[column]=(frame[m+' normalisasi']*weight_frame[m]).where(required[m],0.0).where(complete)
        contributions.append(column)
    frame['Indeks impact']=frame[contributions].sum(axis=1,min_count=len(IMPACT_METRICS))
    frame['Impact'],ib=quantile_scores(frame['Indeks impact'].where(frame['Indeks impact'].gt(0)),[.25,.5,.75],2)
    frame.loc[frame['Indeks impact'].eq(0),'Impact']=1
    frame['Risiko']=frame.Likelihood*frame.Impact
    frame['Status']='Dapat dinilai'
    frame.loc[~complete,'Status']='Data dampak/udara belum lengkap'
    frame.loc[frame.Catatan.eq(0),'Status']='Tidak ada catatan'
    frame.loc[~frame['Pemetaan tersedia'],'Status']='Wilayah BO belum terpetakan'
    frame['Metode']='Persentil berbobot v5.0 — bobot sesuai bencana — udara kategori H+0–H+7 — manusia 50%, lingkungan 50%'
    frame['Aturan sel kosong']='Sel BNPB kosong = 0; udara kosong/tidak cocok tetap tidak tersedia'
    frame['Awal periode']=str(start); frame['Akhir periode']=str(end)
    frame.attrs['bounds']={'Likelihood':lb,'Impact':ib}
    frame.attrs['normalization']=pd.DataFrame([{'Indikator':m,'Bobot Karhutla (%)':KARHUTLA_WEIGHTS[m]*100,'Bobot Selain Karhutla (%)':WEIGHTS[m]*100,'Pasangan lengkap':int((complete & required[m]).sum()),'Pasangan positif':int(frame.loc[complete & required[m],m+' rata-rata'].gt(0).sum())} for m in IMPACT_METRICS])
    return frame

def risk_heatmap(frame,master,metric):
    matrix=frame.pivot(index='BO',columns='Bencana',values=metric).reindex(index=master.BO,columns=HAZARDS).astype(float)
    counts=frame.pivot(index='BO',columns='Bencana',values='Catatan').reindex(index=master.BO,columns=HAZARDS).fillna(0)
    mapped=master.set_index('BO')['ID Kabupaten'].reindex(matrix.index).fillna('').ne('')
    matrix=matrix.mask(counts.eq(0),0).where(mapped,axis=0)
    max_score=25 if metric=='Risiko' else 5
    colors=[[0,'#94a3b8'],[.999/(max_score+1),'#94a3b8'],
            [1/(max_score+1),'#eef2f6'],[1.999/(max_score+1),'#eef2f6'],
            [2/(max_score+1),'#15803d'],[(1+max_score*.5)/(max_score+1),'#facc15'],[1,'#b91c1c']]
    text=[]; hover=[]
    for row in range(len(matrix)):
        labels=[]; details=[]
        for col in range(len(HAZARDS)):
            value=matrix.iloc[row,col]; count=int(counts.iloc[row,col])
            labels.append('N/D' if pd.isna(value) else str(int(value)))
            details.append('Wilayah BO belum cocok dengan BNPB' if not mapped.iloc[row] else 'Tidak ada catatan dalam periode import' if count==0 else ('Belum dapat dinilai: data impact bermasalah' if pd.isna(value) else f'{count} catatan kejadian'))
        text.append(labels); hover.append(details)
    fig=go.Figure(go.Heatmap(z=matrix.fillna(-1).values,x=HAZARDS,y=master.BO.tolist(),
        text=text,texttemplate='%{text}',textfont=dict(size=15),customdata=hover,
        zmin=-1,zmax=max_score,colorscale=colors,xgap=3,ygap=3,
        colorbar=dict(title=metric,tickvals=[0,1,5,10,15,20,25] if metric=='Risiko' else list(range(6))),
        hovertemplate='<b>%{y} · %{x}</b><br>Skor: %{text}<br>%{customdata}<extra></extra>'))
    labels={'Cuaca ekstrem':'Cuaca<br>ekstrem','Tanah longsor':'Tanah<br>longsor','Gempa bumi':'Gempa<br>bumi','Gelombang pasang dan abrasi':'Gelombang pasang<br>dan abrasi','Erupsi gunung api':'Erupsi<br>gunung api'}
    fig.update_xaxes(tickmode='array',tickvals=HAZARDS,ticktext=[labels.get(h,h) for h in HAZARDS],tickangle=0,title=None)
    fig.update_yaxes(autorange='reversed',title=None)
    return fig

def score_boundary_tables(bounds):
    from math import floor
    likelihood=[]
    lb=bounds.get('Likelihood',[])
    for score in range(1,6):
        if not lb:
            interval='Belum tersedia'
        else:
            lower=1 if score==1 else floor(lb[score-2])+1
            upper=floor(lb[score-1]) if score<5 else None
            interval=(f'>= {lower} kejadian' if upper is None else
                      'Tidak ada rentang kejadian' if lower>upper else
                      f'{lower} kejadian' if lower==upper else f'{lower}–{upper} kejadian')
        likelihood.append({'Skor likelihood':score,'Jumlah kejadian':interval})
    impact=[{'Skor impact':1,'Indeks impact (%)':'0%'}]
    ib=bounds.get('Impact',[])
    def percent(value):
        return f'{value:.4f}'.rstrip('0').rstrip('.').replace('.',',')+'%'
    for score in range(2,6):
        if not ib:
            interval='Belum tersedia'
        else:
            lower=0 if score==2 else ib[score-3]
            upper=ib[score-2] if score<5 else None
            interval=(f'> {percent(lower)}' if upper is None else
                      'Tidak ada rentang nilai' if lower>=upper else
                      f'> {percent(lower)} sampai ≤ {percent(upper)}')
        impact.append({'Skor impact':score,'Indeks impact (%)':interval})
    return pd.DataFrame(likelihood),pd.DataFrame(impact)

def render_scoring_details(events,master,start,end,top=False):
    frame=calculate(events,master,start,end)
    with st.expander('Batas Skor Likelihood dan Impact'):
        percentile_rows=[]
        for scale,quantiles in [('Likelihood',[20,40,60,80]),('Impact',[25,50,75])]:
            bounds=frame.attrs['bounds'][scale]
            for index,quantile in enumerate(quantiles):
                value=(f'{bounds[index]:.4f}'.rstrip('0').rstrip('.').replace('.',',')
                       if bounds else 'Belum tersedia')
                if bounds:
                    value+= '' if scale=='Likelihood' else '%'
                percentile_rows.append({'Skala':scale,'Persentil':f'P{quantile}','Batas':value})
        percentile_column,composition_column=st.columns(2)
        with percentile_column:
            st.subheader('Tabel Persentil')
            display_table(pd.DataFrame(percentile_rows),hide_index=True,width='stretch')
        with composition_column:
            st.subheader('Komposisi Impact')
            composition=[{'Indikator':m,'Karhutla':f'{KARHUTLA_WEIGHTS[m]:.0%}','Selain Karhutla':f'{WEIGHTS[m]:.0%}'} for m in IMPACT_METRICS]
            composition.append({'Indikator':'Total','Karhutla':'100%','Selain Karhutla':'100%'})
            display_table(pd.DataFrame(composition),hide_index=True,width='stretch')
        st.divider()
        likelihood_table,impact_table=score_boundary_tables(frame.attrs['bounds'])
        left,right=st.columns(2)
        with left:
            st.subheader('Skor Likelihood')
            display_table(likelihood_table,hide_index=True,width='stretch')
        with right:
            st.subheader('Skor Impact')
            display_table(impact_table,hide_index=True,width='stretch')
    excluded=int((frame.Catatan.gt(0)&frame.Risiko.isna()).sum())
    if excluded: st.warning(f'{excluded} pasangan dengan kejadian belum dapat dinilai risikonya karena indikator yang berlaku belum lengkap. Sel kosong pada kolom yang tersedia sudah dihitung nol; periksa nilai tidak valid, kolom yang hilang, serta cakupan tanggal udara khusus Karhutla. Rumah Terendam tidak berbobot pada Karhutla; udara tidak berbobot pada bencana lainnya.')
    with st.expander('Rincian Kejadian, Dampak, dan Skor'):
        detail=frame[['BO','Bencana','Catatan']+[m+' jumlah' for m in IMPACTS]+[AIR_METRIC+' rata-rata','Indeks impact','Impact','Likelihood']].copy()
        detail=detail.rename(columns={'Catatan':'Kejadian',**{m+' jumlah':m for m in IMPACTS},
            AIR_METRIC+' rata-rata':'Indeks Dampak Udara (0–100)','Indeks impact':'Indeks Impact (%)','Impact':'Skor Impact','Likelihood':'Skor Likelihood'})
        no_events=detail.Kejadian.eq(0)&frame['Pemetaan tersedia']
        detail.loc[no_events,['Indeks Impact (%)','Skor Impact','Skor Likelihood']]=0
        detail_key,detail_base=selection_key('risk_detail_'+str(top))
        table_event=display_table(detail,key=detail_key,on_select='rerun',selection_mode='single-row',hide_index=True,width='stretch',column_config={
            **{m:st.column_config.NumberColumn(m,format='%d') for m in IMPACTS},
            'Indeks Dampak Udara (0–100)':st.column_config.NumberColumn('Indeks Dampak Udara (0–100)',format='%.2f'),
            'Indeks Impact (%)':st.column_config.NumberColumn('Indeks Impact (%)',format='%.4f%%'),
            'Skor Impact':st.column_config.NumberColumn('Skor Impact',format='%d'),
            'Skor Likelihood':st.column_config.NumberColumn('Skor Likelihood',format='%d'),
        })
        if table_event.selection.rows:
            chosen=detail.iloc[table_event.selection.rows[0]]
            if st.button('Hapus pilihan baris',key=detail_key+'_clear'):
                st.session_state[detail_base]=st.session_state.get(detail_base,0)+1
                st.rerun()
            source_panel(events,master,'risk_detail_'+str(top),bo=chosen.BO,hazard=chosen.Bencana,scores=frame)
    return frame

def render(events,master,start,end,chart):
    frame=render_scoring_details(events,master,start,end)
    if frame.empty:
        st.info('Tidak ada jenis bencana pada dataset ini.')
        return
    for tab,metric in zip(st.tabs(['Matrix Likelihood','Matrix Impact','Risiko (L × I)']),['Likelihood','Impact','Risiko']):
        with tab:
            fig=heatmap_targets(risk_heatmap(frame,master,metric),master,HAZARDS)
            selected=selected_chart(fig,max(510,len(master)*32+130),'risk_'+metric)
            if selected: source_panel(events,master,'risk_'+metric,bo=selected[0],hazard=selected[1],scores=frame)
