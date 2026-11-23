"""Shared presentation: tables, chart selections, page headers and analysis period."""
from dataclasses import replace
from datetime import date,datetime
from html import escape
from types import SimpleNamespace
import hashlib,inspect,math,numbers
import pandas as pd
import streamlit as st
from data_engine import AIR_METRIC,IMPACTS,HAZARDS,bcp_events,csv_bytes,prepare,attach_air,master_signature,branches


TABLE_CSS = '''
.bcp-table-wrap {max-height:480px;overflow:auto;border:1px solid #bdcde0;border-radius:12px;background:white;font-family:"Segoe UI",Arial,sans-serif;color:#18334a;}
.bcp-table {border-collapse:separate;border-spacing:0;table-layout:fixed;width:100%;overflow-wrap:anywhere;font-size:15px;line-height:1.55;}
.bcp-table td,.bcp-table th {padding:10px 12px;border-bottom:1px solid #dce5ef;border-right:1px solid #e4ebf3;vertical-align:top;overflow-wrap:anywhere;text-align:left;}
.bcp-table tbody tr:nth-child(even) {background:#f4f8fd;}
.bcp-table tbody tr:hover {background:#eaf3ff;}
.bcp-table th {position:sticky;top:0;z-index:1;background:#dbeafe;color:#12375e;font-weight:750;text-align:left;border-bottom:2px solid #9fbadd;}
.bcp-table th,.bcp-table td {padding:11px 13px;border-right:1px solid #d7e2f0;border-bottom:1px solid #d7e2f0;overflow-wrap:anywhere;vertical-align:top;box-sizing:border-box;}
.bcp-table tbody tr:nth-child(even) {background:#f1f6ff;}
.bcp-table tbody tr:hover {background:#e2eeff;}
.bcp-table .number {text-align:right;font-variant-numeric:tabular-nums;}
.bcp-table tr[tabindex] {cursor:pointer;}
.bcp-table tr[tabindex]:focus {outline:3px solid #2563eb;outline-offset:-3px;}
.bcp-table tr[aria-selected="true"] {background:#d9eaff!important;box-shadow:inset 4px 0 #2563eb;}
.bcp-table-empty {padding:16px;color:#435a73;}
'''

def column_width(name):
    if name=='BO': return 140
    if name in ('Alamat','Lokasi','Penyebab','Masalah','Alasan'): return 360
    if name in ('Kabupaten/Kota','Kabupaten','Provinsi','Bencana'): return 205
    if name in ('Batas','Jumlah kejadian','Indeks impact (%)','Indeks Impact (%)'): return 225
    if 'Tanggal' in name or name in ('Indikator','Skala'): return 165
    if name in ('Informasi','Nilai'): return 240
    return max(140,min(230,len(name)*9+30))

def format_cell(value,name,config):
    if pd.isna(value): return '—'
    if isinstance(value,(pd.Timestamp,date,datetime)):
        return value.strftime('%d/%m/%Y')
    if isinstance(value,numbers.Real) and not isinstance(value,bool):
        fmt=config.get('type_config',{}).get('format')
        if fmt and '%' in fmt:
            try: return fmt % value
            except (ValueError,TypeError): pass
        if 'Indeks Impact (%)'==name: return f'{value:.4f}%'
        return str(int(value)) if math.isfinite(value) and float(value).is_integer() else f'{value:.4f}'.rstrip('0').rstrip('.')
    return str(value)

def table_markup(data,column_config=None,selectable=False):
    frame=pd.DataFrame(data)
    config=column_config or {}
    widths=[column_width(str(c)) for c in frame.columns]
    parts=['<div class="bcp-table-wrap"><table class="bcp-table" style="min-width:'+str(sum(widths))+'px">']
    parts.append('<colgroup>'+''.join('<col style="width:'+str(w)+'px">' for w in widths)+'</colgroup>')
    parts.append('<thead><tr>'+''.join('<th scope="col">'+escape(str((config.get(c) or {}).get('label') or c))+'</th>' for c in frame.columns)+'</tr></thead><tbody>')
    for index,row in enumerate(frame.itertuples(index=False,name=None)):
        attributes=f' data-row="{index}" tabindex="0" aria-selected="false"' if selectable else ''
        parts.append('<tr'+attributes+'>')
        for name,value in zip(frame.columns,row):
            number=isinstance(value,numbers.Real) and not isinstance(value,bool)
            text=escape(format_cell(value,str(name),config.get(name) or {}))
            parts.append('<td'+(' class="number"' if number else '')+'>'+text+'</td>')
        parts.append('</tr>')
    parts.append('</tbody></table>')
    if frame.empty: parts.append('<div class="bcp-table-empty">Tidak ada data untuk ditampilkan.</div>')
    parts.append('</div>')
    return ''.join(parts)

def selectable_component():
    return st.components.v2.component('bcp_fixed_table',css=TABLE_CSS,js='''
    export default function(component) {
      const {parentElement, data, setStateValue} = component;
      let root=parentElement.querySelector('.bcp-table-root');
      if(!root){root=document.createElement('div');root.className='bcp-table-root';parentElement.appendChild(root);}
      root.innerHTML = data.html;
      const rows=root.querySelectorAll('[data-row]');
      for (const row of rows) {
        const choose=()=>{
          for(const other of rows) other.setAttribute('aria-selected','false');
          row.setAttribute('aria-selected','true');
          setStateValue('row',Number(row.dataset.row));
        };
        row.onclick=choose;
        row.onkeydown=(event)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose();}};
        if(Number(row.dataset.row)===data.selected) row.setAttribute('aria-selected','true');
      }
    }
    ''')

def display_table(data,*,hide_index=True,width='stretch',column_config=None,key=None,on_select='ignore',selection_mode=None,**kwargs):
    selectable=on_select!='ignore'
    html=table_markup(data,column_config,selectable)
    if not selectable:
        st.html('<style>'+TABLE_CSS+'</style>'+html)
        return None
    if key is None:
        caller=inspect.currentframe().f_back
        key='table_'+hashlib.sha256(f'{caller.f_code.co_filename}:{caller.f_lineno}'.encode()).hexdigest()[:10]
    previous=st.session_state.get(key,{})
    selected=previous.get('row') if hasattr(previous,'get') else None
    if selected is not None and not 0<=selected<len(data): selected=None
    state=selectable_component()(key=key,data={'html':html,'selected':selected},default={'row':None},
        on_row_change=lambda:None,width='stretch')
    selected=state.row
    rows=[selected] if isinstance(selected,int) and 0<=selected<len(data) else []
    return SimpleNamespace(selection=SimpleNamespace(rows=rows))

def selection_key(name):
    active=st.session_state.get('v02_active',{})
    selected=st.session_state.get('v02_analysis_selection',{})
    identity=(active.get('activated',''),selected.get('start'),selected.get('end'))
    token=hashlib.sha256(str(identity).encode()).hexdigest()[:10]
    base=f'drill_{token}_{name}'
    return base+'_'+str(st.session_state.get(base,0)),base

def fixed_chart_layout(fig,height):
    horizontal=[trace for trace in fig.data if trace.type=='bar' and trace.orientation=='h']
    if horizontal:
        count=max(len(trace.y) for trace in horizontal)
        height=max(height,115+count*34)
        fig.update_yaxes(autorange=True,automargin=True,tickfont=dict(size=15,color='#243b53'),dtick=1)
        fig.update_xaxes(autorange=True,automargin=True)
        for trace in horizontal:
            trace.update(textposition='outside',textangle=0,cliponaxis=False,textfont=dict(size=15,color='#142d50'))
    fig.update_layout(height=height,dragmode=False,
        margin=dict(l=20,r=55,t=45,b=65),
        font=dict(family='Segoe UI, Arial',size=16,color='#142d50'),
        paper_bgcolor='#ffffff',plot_bgcolor='#ffffff',
        hoverlabel=dict(bgcolor='#142d50',font=dict(color='#ffffff',size=15)),
        legend=dict(font=dict(size=15,color='#243b53')),
        uirevision=None)
    fig.update_xaxes(fixedrange=True,automargin=True,tickfont=dict(size=15,color='#243b53'),title_font=dict(size=16,color='#243b53'),gridcolor='#dce5ef',zeroline=False)
    fig.update_yaxes(fixedrange=True,automargin=True,tickfont=dict(size=15,color='#243b53'),title_font=dict(size=16,color='#243b53'),gridcolor='#e5ecf4',zeroline=False)
    return fig

FIXED_CHART_CONFIG={'displaylogo':False,'modeBarButtons':[['toImage']],
    'scrollZoom':False,'doubleClick':False,'showAxisDragHandles':False,
    'toImageButtonOptions':{'format':'png','filename':'BCP_Atlas','scale':2}}

def selected_chart(fig,height,name):
    key,base=selection_key(name)
    fixed_chart_layout(fig,height)
    fig.update_layout(clickmode='event+select',paper_bgcolor='#ffffff')
    st.caption('Klik grafik untuk melihat ringkasan data.' if name=='overview_bo' else 'Klik batang atau penanda untuk membuka data sumber di bawah grafik.')
    event=st.plotly_chart(fig,key=key,width='stretch',on_select='rerun',
        selection_mode='points',config=FIXED_CHART_CONFIG)
    points=event.selection.points
    if points:
        if st.button('Hapus pilihan',key=key+'_clear'):
            st.session_state[base]=st.session_state.get(base,0)+1
            st.rerun()
        return points[-1].get('customdata')
    return None

def heatmap_targets(fig,master,hazards):
    # Streamlit selection supports scatter points, not native heatmap cells.
    # Put selectable targets over the cells while preserving the original heatmap.
    import plotly.graph_objects as go
    pairs=[(bo,hazard) for bo in master.BO for hazard in hazards]
    fig.add_trace(go.Scatter(x=[h for b,h in pairs],y=[b for b,h in pairs],
        mode='markers',marker=dict(size=24,color='rgba(255,255,255,0.015)',symbol='square'),
        customdata=[[b,h] for b,h in pairs],showlegend=False,
        hovertemplate='<b>%{customdata[0]} · %{customdata[1]}</b><br>Klik untuk melihat rincian<extra></extra>',
        selected=dict(marker=dict(opacity=1,color='#38bdf8')),
        unselected=dict(marker=dict(opacity=.015))))
    return fig

def selection_summary(data,master,group):
    if group=='bencana':
        counts=data.Bencana.value_counts().reindex(HAZARDS,fill_value=0)
        return counts.rename_axis('Bencana').reset_index(name='Jumlah Kejadian')
    if group=='bo':
        counts=data.groupby('Kode wilayah').size()
        result=master[['BO','ID Kabupaten']].copy()
        result['Jumlah Kejadian']=result['ID Kabupaten'].map(counts).fillna(0).astype(int)
        return result.loc[result['Jumlah Kejadian'].gt(0),['BO','Jumlah Kejadian']].sort_values('Jumlah Kejadian',ascending=False,kind='stable').reset_index(drop=True)
    raise ValueError('Jenis ringkasan tidak dikenali')

def source_panel(events,master,name,bo=None,hazard=None,month=None,scores=None,summary_by=None):
    data=bcp_events(events)
    labels=[]
    if bo:
        selected=master[master.BO.eq(bo)]
        data=data[data['Kode wilayah'].isin(selected['ID Kabupaten'])]
        labels.append(bo)
    if hazard:
        data=data[data.Bencana.eq(hazard)]
        labels.append(hazard)
    if month:
        data=data[data.Tanggal.dt.strftime('%Y-%m').eq(str(month)[:7])]
        labels.append(str(month)[:7])
    karhutla_only=hazard=='Karhutla' or (not data.empty and data.Bencana.eq('Karhutla').all())
    with st.container(border=True,key='detail_panel_'+name):
        st.subheader('Detail Pilihan · '+' / '.join(labels))
        st.metric('Jumlah Kejadian',len(data))
        if scores is not None:
            row=scores[scores.BO.eq(bo)&scores.Bencana.eq(hazard)]
            if not row.empty:
                row=row.iloc[0]
                cols=st.columns(3)
                for col,field in zip(cols,['Likelihood','Impact','Risiko']):
                    value=row[field]
                    col.metric(field,'N/D' if not row.get('Pemetaan tersedia',True) else '0' if not len(data) else ('N/D' if pd.isna(value) else str(int(value))))
                st.caption('Skor berasal dari perhitungan seluruh dataset aktif. Pilihan grafik hanya membuka rincian data.')
        if data.empty:
            st.info('Tidak ada catatan untuk pilihan ini pada periode aktif; bukan bukti nihil risiko.')
        else:
            totals=[]
            value_column='Nilai' if karhutla_only else 'Jumlah tercatat'
            metrics=[m for m in IMPACTS if not (karhutla_only and m=='Rumah Terendam')]
            for metric in metrics:
                valid=data[metric].dropna()
                totals.append({'Indikator':metric,value_column:None if valid.empty else float(valid.sum())})
            if karhutla_only:
                valid_air=data[AIR_METRIC].dropna() if AIR_METRIC in data else pd.Series(dtype=float)
                air_index=float(valid_air.mean()) if len(valid_air)==len(data) else None
                totals.append({'Indikator':'Indeks Dampak Udara (0–100)',value_column:None if air_index is None else round(air_index,2)})
            display_table(pd.DataFrame(totals),hide_index=True,width='stretch')
            if AIR_METRIC in data and data.Bencana.eq('Karhutla').any() and not karhutla_only:
                fire_data=data[data.Bencana.eq('Karhutla')]
                valid_air=fire_data[AIR_METRIC].dropna()
                st.metric('Indeks Dampak Udara (0–100)','N/D' if len(valid_air)!=len(fire_data) else f'{valid_air.mean():.2f}')
                st.caption(f'Udara H+0–H+7 lengkap pada {len(valid_air):,}/{len(fire_data):,} kejadian Karhutla; Good = 0; kategori dan durasi dihitung bersama, bukan nilai AQI mentah.')
        if summary_by:
            st.subheader('Jumlah kejadian per jenis bencana' if summary_by=='bencana' else 'Jumlah kejadian per wilayah')
            display_table(selection_summary(data,master,summary_by),hide_index=True,width='stretch')
        else:
            metrics=[m for m in IMPACTS if not (karhutla_only and m=='Rumah Terendam')]
            columns=['Tanggal','Bencana','Provinsi','Kabupaten','Lokasi']+metrics
            if karhutla_only: columns.append('AQI 8 hari rata-rata')
            evidence=data.reindex(columns=columns).sort_values('Tanggal',ascending=False)
            evidence=evidence.rename(columns={'AQI 8 hari rata-rata':'AQI rata-rata 8 hari'})
            display_table(evidence.head(200),hide_index=True,width='stretch')
            if len(evidence)>200: st.caption('Menampilkan 200 baris pertama dari hasil pilihan.')

PIE_JS = '''
export default function(component) {
  const {parentElement,data,setStateValue}=component;
  let host=parentElement.querySelector('.pie-host');
  if(!host){host=document.createElement('div');host.className='pie-host';parentElement.appendChild(host);}
  host.replaceChildren();
  host.style.cssText=`height:${data.height}px;position:relative;width:100%;`;
  const ns='http://www.w3.org/2000/svg';
  const svg=document.createElementNS(ns,'svg');
  const height=410+data.items.length*28;
  svg.setAttribute('viewBox',`0 0 540 ${height}`);
  svg.setAttribute('role','group');svg.setAttribute('aria-label','Komposisi Bencana');
  svg.style.cssText='display:block;width:100%;height:100%;background:white;font-family:Segoe UI,Arial,sans-serif';
  const add=(tag,attrs,text,parent=svg)=>{const el=document.createElementNS(ns,tag);for(const [key,value] of Object.entries(attrs))el.setAttribute(key,value);if(text!==undefined)el.textContent=text;parent.appendChild(el);return el;};
  add('rect',{x:0,y:0,width:540,height,fill:'white'});
  add('text',{x:270,y:28,'text-anchor':'middle',fill:'#173e70','font-size':20,'font-weight':700});
  const total=data.items.reduce((sum,item)=>sum+item.value,0);
  const polar=(r,a)=>[270+r*Math.cos(a),210+r*Math.sin(a)];
  let angle=-Math.PI/2;
  for(const [index,item] of data.items.entries()) {
    const portion=item.value/total;
    const finish=angle+portion*2*Math.PI;
    const [x1,y1]=polar(155,angle),[x2,y2]=polar(155,finish);
    let slice;
    if(portion>=1) slice=add('circle',{cx:270,cy:210,r:155,fill:item.color});
    else slice=add('path',{d:`M270,210 L${x1},${y1} A155,155 0 ${portion>.5?1:0},1 ${x2},${y2} Z`,fill:item.color});
    const label=`${item.label}: ${item.value} kejadian (${(portion*100).toFixed(2)}%)`;
    slice.setAttribute('stroke',item.label===data.selected?'#102d50':'#ffffff');
    slice.setAttribute('stroke-width',item.label===data.selected?4:2);
    slice.setAttribute('tabindex','0');slice.setAttribute('role','button');slice.setAttribute('aria-label',label);
    slice.style.cursor='pointer';add('title',{},label,slice);
    const choose=()=>setStateValue('selected',item.label);
    const keyboard=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};
    slice.onclick=choose;slice.onkeydown=keyboard;
    if(portion>=.055){const [x,y]=polar(107,(angle+finish)/2);add('text',{x,y,'text-anchor':'middle','dominant-baseline':'middle','font-size':22,'font-weight':700,fill:item.color==='#E58B0A'?'#102d50':'#ffffff','pointer-events':'none'},`${Math.round(portion*100)}%`);}
    const row=add('g',{tabindex:0,role:'button','aria-label':label});
    row.style.cursor='pointer';row.onclick=choose;row.onkeydown=keyboard;
    add('rect',{x:20,y:394+index*28,width:500,height:27,fill:item.label===data.selected?'#e4efff':'white',rx:5},undefined,row);
    add('circle',{cx:35,cy:407+index*28,r:6,fill:item.color},undefined,row);
    add('text',{x:52,y:413+index*28,fill:'#173e70','font-size':19},item.label, row);
    add('text',{x:505,y:413+index*28,fill:'#173e70','font-size':19,'text-anchor':'end','font-weight':650},String(item.value),row);
    angle=finish;
  }
  const button=document.createElement('button');button.textContent='↓ PNG';button.title='Unduh grafik PNG';
  button.style.cssText='position:absolute;right:4px;top:4px;z-index:2;border:1px solid #b8c9dd;border-radius:7px;background:white;color:#173e70;padding:5px 10px;cursor:pointer';
  button.onclick=()=>{
    const blob=new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml;charset=utf-8'});
    const url=URL.createObjectURL(blob),img=new Image();
    img.onload=()=>{const canvas=document.createElement('canvas');canvas.width=1080;canvas.height=height*2;const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);const link=document.createElement('a');link.download='Komposisi_Bencana.png';link.href=canvas.toDataURL('image/png');link.click();URL.revokeObjectURL(url);};
    img.onerror=()=>URL.revokeObjectURL(url);img.src=url;
  };
  host.appendChild(button);host.appendChild(svg);
}
'''

def selected_pie(counts,colors,name='overview_hazard_pie',height=523):
    key,base=selection_key(name)
    items=[{'label':str(row['Bencana']),'value':int(row['Catatan kejadian']),'color':colors[i%len(colors)]}
           for i,(_,row) in enumerate(counts.iterrows()) if row['Catatan kejadian']>0]
    st.caption('Klik grafik untuk melihat ringkasan data.')
    previous=st.session_state.get(key,{})
    selected=previous.get('selected') if hasattr(previous,'get') else None
    component=st.components.v2.component('bcp_composition_pie',js=PIE_JS)
    result=component(key=key,data={'items':items,'selected':selected,'height':height},height=height,width='stretch',default={'selected':None},on_selected_change=lambda:None)
    selected=result.selected
    if selected in [item['label'] for item in items]:
        if st.button('Hapus pilihan',key=key+'_clear'):
            st.session_state[base]=st.session_state.get(base,0)+1
            st.rerun()
        return [selected]
    return None

def source_period(raw):
    text=raw['Tanggal Kejadian'].astype(str).str.strip()
    iso=text.str.match(r'^\d{4}-\d{2}-\d{2}(?:[ T].*)?$')
    dates=pd.to_datetime(text,format='mixed',dayfirst=True,errors='coerce')
    dates.loc[iso]=pd.to_datetime(text[iso],format='ISO8601',errors='coerce')
    valid=dates.dropna()
    if valid.empty: raise ValueError('File BNPB tidak memiliki tanggal valid.')
    return valid.min().date(),valid.max().date()

def _date(value):
    if value is None or pd.isna(value): raise ValueError('Pilih tanggal awal dan tanggal akhir terlebih dahulu.')
    try: parsed=pd.Timestamp(value)
    except (ValueError,TypeError) as exc: raise ValueError('Tanggal analisis tidak valid.') from exc
    if pd.isna(parsed): raise ValueError('Pilih tanggal awal dan tanggal akhir terlebih dahulu.')
    return parsed.date()

def validate_period(start,end,minimum,maximum):
    start,end=_date(start),_date(end)
    if start>end: raise ValueError('Tanggal awal harus sebelum atau sama dengan tanggal akhir.')
    if start<minimum or end>maximum:
        raise ValueError(f'Periode harus berada dalam cakupan file BNPB: {minimum:%d/%m/%Y}–{maximum:%d/%m/%Y}.')
    return start,end

def analysis_context(active,master,state=None):
    state=st.session_state if state is None else state
    minimum,maximum=source_period(active['result'].raw)
    dataset_id=active.setdefault('dataset_id',active['activated'])
    selected=state.get('v02_analysis_selection')
    if not selected or selected.get('dataset_id')!=dataset_id:
        start=max(minimum,min(_date(active['start']),maximum))
        end=max(start,min(_date(active['end']),maximum))
        selected={'dataset_id':dataset_id,'start':start,'end':end}
        state['v02_analysis_selection']=selected
        for key in ['analysis_period_start','analysis_period_end','v02_period_widget_context']:
            state.pop(key,None)
    start,end=validate_period(selected['start'],selected['end'],minimum,maximum)
    air=active.get('air')
    air_token=(air.meta.get('sha256') or hashlib.sha256(air.raw.to_json().encode()).hexdigest()) if air is not None else None
    cache_key=('full-bnpb-v1',dataset_id,master_signature(master),air_token,bool(active.get('dedup')),minimum,maximum)
    if active.get('analysis_cache_key')!=cache_key:
        full=prepare(active['result'].raw,minimum,maximum,active.get('dedup',False),master=master)
        active['analysis_full_events']=attach_air(full.events,air.daily if air is not None else None)
        active['analysis_cache_key']=cache_key
    events=active['analysis_full_events']
    filtered=events.loc[events.Tanggal.between(pd.Timestamp(start),pd.Timestamp(end))].copy()
    return {'start':start,'end':end,'minimum':minimum,'maximum':maximum,'events':filtered,'dataset_id':dataset_id}

def set_analysis_period(active,master,start,end,state=None):
    state=st.session_state if state is None else state
    minimum,maximum=source_period(active['result'].raw)
    start,end=validate_period(start,end,minimum,maximum)
    dataset_id=active.setdefault('dataset_id',active['activated'])
    state['v02_analysis_selection']={'dataset_id':dataset_id,'start':start,'end':end}
    for key in list(state):
        if key=='report_file' or key.startswith(('drill_','bcp_assistant_answer','bcp_assistant_pending','bcp_assistant_token')):
            state.pop(key,None)
    return analysis_context(active,master,state)

def render_period_control(active,master,context,page):
    identity=(context['dataset_id'],page)
    if st.session_state.get('v02_period_widget_context')!=identity:
        st.session_state['analysis_period_start']=context['start']
        st.session_state['analysis_period_end']=context['end']
        st.session_state['v02_period_widget_context']=identity
    st.session_state.setdefault('analysis_period_start',context['start'])
    st.session_state.setdefault('analysis_period_end',context['end'])
    with st.container(border=True,key='analysis_period_panel'):
        st.markdown('**Periode data**')
        with st.form('shared_analysis_period',border=False):
            left,right,action=st.columns([1,1,1],gap='medium',vertical_alignment='bottom')
            with left:
                start=st.date_input('Tanggal awal',key='analysis_period_start',
                    min_value=context['minimum'],max_value=context['maximum'],format='DD/MM/YYYY')
            with right:
                end=st.date_input('Tanggal akhir',key='analysis_period_end',
                    min_value=context['minimum'],max_value=context['maximum'],format='DD/MM/YYYY')
            with action:
                submitted=st.form_submit_button('Terapkan periode',type='primary',width='stretch')
        if submitted:
            try:
                set_analysis_period(active,master,start,end)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        st.markdown(
            f'<div class="period-meta"><span class="period-active">Aktif: {context["start"]:%d/%m/%Y} – {context["end"]:%d/%m/%Y}</span>'
            f'<span class="period-source">Cakupan file: {context["minimum"]:%d/%m/%Y} – {context["maximum"]:%d/%m/%Y}</span></div>',
            unsafe_allow_html=True)

def assistant_view(active,context):
    result=dict(active)
    result['result']=replace(active['result'],events=context['events'])
    result['start'],result['end']=context['start'],context['end']
    return result

COLORS = ['#2563EB','#089981','#E58B0A','#7C3AED','#DB2777','#0284C7','#475569','#C65B14','#4D7C0F']

def hero(page, subtitle, active, master=None):
    master=branches() if master is None else master
    label = 'DATA AKTIF' if active else 'SIAP MENERIMA DATA'
    source = escape(active['meta']['file']) if active else 'Upload Excel / CSV untuk memulai analisis'
    st.markdown(f'''<div class="hero"><div class="hero-copy"><div class="eyebrow">ENTERPRISE RISK MANAGEMENT &nbsp; / &nbsp; BUSINESS CONTINUITY PLAN
    </div>
    <h1>{escape(page)}</h1><p>{escape(subtitle)}</p><div class="hero-tags"><span>{len(master)} Business Operation</span><span>Analisis kabupaten / kota</span><span>Workspace v0.3</span></div></div>
    <div class="hero-status"><span class="status-dot"></span> {label}<small>{source}</small></div></div>''', unsafe_allow_html=True)

def workflow(active,master=None):
    master=branches() if master is None else master
    st.markdown(f'''<div class="workflow"><div><b>01</b><span>UPLOAD DATA<small>Excel / CSV • deteksi otomatis</small></span></div><i>→</i><div><b>02</b><span>MAPPING WILAYAH<small>Validasi {len(master)} lokasi operasional</small></span></div><i>→</i><div><b>03</b><span>ANALISIS & LAPORAN<small>Filter • visualisasi • ekspor</small></span></div></div>''', unsafe_allow_html=True)

def fmt(value): return '—' if pd.isna(value) else f'{value:,.0f}'.replace(',','.')

def chart(fig,height=340):
    fig.update_layout(height=height,margin=dict(l=10,r=10,t=20,b=15),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(family='Segoe UI, Arial',color='#516781'),colorway=COLORS,hoverlabel=dict(bgcolor='#142d50',font_color='white'),legend_title_text='' )
    fig.update_xaxes(showgrid=True,gridcolor='#e8eef6',zeroline=False)
    fig.update_yaxes(gridcolor='#e8eef6',zeroline=False)
    fixed_chart_layout(fig,height)
    st.plotly_chart(fig,width='stretch',config=FIXED_CHART_CONFIG)
