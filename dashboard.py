import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

# ============================================
# CONFIGURAÇÕES DE ACESSO - PRODUÇÃO
# ============================================
try:
    TRELLO_API_KEY = st.secrets["TRELLO_API_KEY"]
    TRELLO_TOKEN = st.secrets["TRELLO_TOKEN"]
    BOARD_ID = st.secrets["BOARD_ID"]
except:
    st.error("""
    ### 🔐 Erro de Configuração
    
    **Secrets não encontrados!** 
    
    Configure no Streamlit Cloud:
    1. Settings → Secrets
    2. Adicione:
    ```
    TRELLO_API_KEY = "sua_chave"
    TRELLO_TOKEN = "seu_token"
    BOARD_ID = "7xxYbkwX"
    ```
    """)
    st.stop()

# ============================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================
st.set_page_config(
    page_title="Dashboard Trello - Delphi10 QA",
    page_icon="📊",
    layout="wide"
)

# ============================================
# FUNÇÃO PARA BUSCAR DADOS
# ============================================
@st.cache_data(ttl=300)
def fetch_trello_data():
    """Busca todos os cards do Trello com paginação"""
    
    try:
        # Buscar listas
        lists_url = f"https://api.trello.com/1/boards/{BOARD_ID}/lists"
        lists_response = requests.get(
            lists_url,
            params={'key': TRELLO_API_KEY, 'token': TRELLO_TOKEN},
            timeout=30
        )
        lists_response.raise_for_status()
        lists_dict = {lst['id']: lst['name'] for lst in lists_response.json()}
        
        # Buscar labels
        labels_url = f"https://api.trello.com/1/boards/{BOARD_ID}/labels"
        labels_response = requests.get(
            labels_url,
            params={'key': TRELLO_API_KEY, 'token': TRELLO_TOKEN},
            timeout=30
        )
        labels_response.raise_for_status()
        labels_dict = {lb['id']: lb['name'] for lb in labels_response.json()}
        
        # Buscar cards com paginação
        cards_url = f"https://api.trello.com/1/boards/{BOARD_ID}/cards"
        all_cards = []
        offset = 0
        
        while True:
            cards_response = requests.get(
                cards_url,
                params={
                    'key': TRELLO_API_KEY,
                    'token': TRELLO_TOKEN,
                    'fields': 'id,name,idList,dateLastActivity,idLabels',
                    'limit': 1000,
                    'offset': offset
                },
                timeout=30
            )
            cards_response.raise_for_status()
            
            batch = cards_response.json()
            if not batch:
                break
                
            all_cards.extend(batch)
            
            if len(batch) < 1000:
                break
                
            offset += 1000
        
        # Processar cards
        cards_list = []
        for card in all_cards:
            # Processar labels
            card_labels = []
            for label_id in card.get('idLabels', []):
                label_name = labels_dict.get(label_id)
                if label_name:
                    card_labels.append(label_name)
            
            cards_list.append({
                'id': card.get('id', ''),
                'name': card.get('name', 'Sem título'),
                'list': lists_dict.get(card.get('idList'), 'Sem Lista'),
                'labels': ', '.join(card_labels) if card_labels else 'Sem Etiqueta',
                'dateLastActivity': card.get('dateLastActivity', '')
            })
        
        # Criar DataFrame
        df = pd.DataFrame(cards_list)
        
        if not df.empty:
            df['dateLastActivity'] = pd.to_datetime(df['dateLastActivity'], errors='coerce')
            df = df.sort_values('dateLastActivity', ascending=False)
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return None

# ============================================
# DASHBOARD PRINCIPAL
# ============================================
def main():
    st.title("📊 Dashboard Trello - Problemas Delphi10 QA")
    
    # Sidebar
    with st.sidebar:
        st.header("🎯 Controles")
        
        if st.button("🔄 Buscar Dados", type="primary", use_container_width=True):
            with st.spinner("Buscando cards do Trello..."):
                st.cache_data.clear()
                df = fetch_trello_data()
                if df is not None and not df.empty:
                    st.session_state.df = df
                    st.session_state.last_update = datetime.now()
                    st.success(f"✅ {len(df)} cards carregados!")
                    st.rerun()
        
        if 'last_update' in st.session_state:
            st.caption(f"🕒 Última atualização: {st.session_state.last_update.strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Carregar dados
    if 'df' not in st.session_state:
        df = fetch_trello_data()
        if df is not None:
            st.session_state.df = df
            st.session_state.last_update = datetime.now()
    
    if 'df' not in st.session_state or st.session_state.df.empty:
        st.warning("Clique em 'Buscar Dados' na barra lateral para carregar os cards.")
        return
    
    df = st.session_state.df
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(df)
    concluidos = len(df[df['list'].str.contains('Conclu|Funcion|Done|Finished', case=False, na=False)])
    
    col1.metric("📋 Total", total)
    col2.metric("✅ Concluídos", concluidos)
    col3.metric("⏳ Pendentes", total - concluidos)
    col4.metric("📊 Taxa", f"{concluidos/total*100:.1f}%" if total > 0 else "0%")
    
    st.divider()
    
    # Gráficos
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("📊 Distribuição por Lista")
        list_counts = df['list'].value_counts().head(15)
        if not list_counts.empty:
            fig = px.pie(
                values=list_counts.values,
                names=list_counts.index,
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
    
    with col_right:
        st.subheader("🏷️ Top 15 Etiquetas")
        if 'labels' in df.columns:
            df_labels = df.assign(labels=df['labels'].str.split(', ')).explode('labels')
            df_labels = df_labels[df_labels['labels'] != 'Sem Etiqueta']
            
            if not df_labels.empty:
                label_counts = df_labels['labels'].value_counts().head(15)
                fig = px.bar(
                    x=label_counts.values,
                    y=label_counts.index,
                    orientation='h',
                    color=label_counts.values,
                    color_continuous_scale='Viridis',
                    text=label_counts.values
                )
                fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                fig.update_traces(textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Tabela
    st.subheader(f"🔍 Cards ({len(df)} total)")
    
    search = st.text_input("Pesquisar por nome, lista ou etiqueta")
    
    filtered_df = df.copy()
    if search:
        mask = (
            filtered_df['name'].str.contains(search, case=False, na=False) |
            filtered_df['list'].str.contains(search, case=False, na=False) |
            filtered_df['labels'].str.contains(search, case=False, na=False)
        )
        filtered_df = filtered_df[mask]
    
    st.dataframe(
        filtered_df[['name', 'list', 'labels', 'dateLastActivity']],
        use_container_width=True,
        height=500,
        column_config={
            "name": "Nome do Cartão",
            "list": "Lista",
            "labels": "Etiquetas",
            "dateLastActivity": st.column_config.DatetimeColumn(
                "Última Atividade",
                format="DD/MM/YYYY HH:mm"
            )
        },
        hide_index=True
    )

if __name__ == "__main__":
    main()