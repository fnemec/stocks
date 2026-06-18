import io
from datetime import date
import pandas as pd
import streamlit as st

COLS = ["ticker", "operacao", "preco", "quantidade", "data" ]

def new_empty_df() -> pd.DataFrame:
    return ensure_schema(pd.DataFrame(columns=COLS))

def render_sidebar_import_export() -> None:
    st.sidebar.header("Dados")
    uploaded = st.sidebar.file_uploader("Importar CSV", type=["csv"])
    if uploaded is not None:
        try:
            imported = pd.read_csv(uploaded)
            imported = ensure_schema(imported)
            st.session_state.ops = pd.concat([st.session_state.ops, imported], ignore_index=True)
            st.session_state.msg = f"Importado: {len(imported)} registro(s)."
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Falha ao importar CSV: {e}")

    st.sidebar.download_button(
        "Baixar operações (CSV)",
        data=df_to_csv_bytes(st.session_state.ops),
        file_name="operacoes.csv",
        mime="text/csv",
    )
    st.sidebar.caption("Colunas: ticker, operacao, preco, quantidade, data")

def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Garante colunas e tipos básicos; converte data para datetime"""
    for c in COLS:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[COLS].copy()
    df["ticker"] = df["ticker"].astype("string")
    df["operacao"] = df["operacao"].astype("string")
    df["preco"] = pd.to_numeric(df["preco"], errors="coerce")
    df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").astype("Int64")
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    return df

def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Exporta o DF como CSV (data em YYYY-MM-DD)."""
    buf = io.StringIO()
    out = df.copy()
    out["data"] = out["data"].dt.date.astype("string")
    out.to_csv(buf, index=False, encoding="utf-8")
    return buf.getvalue().encode("utf-8")

def render_tabela_e_filtros() -> None:
    st.subheader("🗂️ Operações registradas")
    df = st.session_state.ops.copy()
    f1, f2 = st.columns(2)

    with f1:
        tickers = sorted([t for t in df["ticker"].dropna().unique().tolist() if str(t).strip()])
        ticker_sel = st.multiselect("Ticker(s)", tickers, default=[])
    with f2:
        op_sel = st.multiselect("Operação", ["compra", "venda"], default=[])

    filtered = df.copy()
    if ticker_sel:
        filtered = filtered[ filtered["ticker"].isin(ticker_sel) ]
    if op_sel:
        filtered = filtered[ filtered["operacao"].isin(op_sel) ]

    show = filtered.copy()
    show["data"] = show["data"].dt.date.astype("string")
    st.dataframe(show, use_container_width=True, hide_index=True)

def render_posicao_carteira() -> None:
    st.subheader("🧾 Posição da carteira (por ticker)")
    df = st.session_state.ops.copy()
    pos = compute_posicao_carteira(df)

    if pos.empty:
        st.info("Ainda não há operações suficientes para calcular a posição.")
        return

    st.dataframe(pos, use_container_width=True, hide_index=True)
    # Métricas rápidas (opcional e leve)
    total_tickers = len(pos)
    total_qtd = int(pos["quantidade"].sum())
    c1, c2 = st.columns(2)
    c1.metric("Tickers na carteira", total_tickers)
    c2.metric("Quantidade líquida (soma)", total_qtd)


def compute_posicao_carteira(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula posição por ticker:
    - compras somam quantidade
    - vendas subtraem quantidade
    Retorna DataFrame com colunas: ticker, quantidade
    """
    if df.empty:
        return pd.DataFrame(columns=["ticker", "quantidade"])

    clean = df.dropna(subset=["ticker", "operacao", "quantidade"]).copy()
    clean["operacao"] = clean["operacao"].str.lower()

    # sinal: compra +1, venda -1 (qualquer outra coisa vira NaN e some)
    clean["sinal"] = clean["operacao"].map({"compra": 1, "venda": -1})
    clean = clean.dropna(subset=["sinal"])
    clean["quantidade_signed"] = clean["quantidade"].astype("int64") * clean["sinal"].astype("int64")
    pos = (
        clean.groupby("ticker", as_index=False)["quantidade_signed"]
        .sum()
        .rename(columns={"quantidade_signed": "quantidade"})
        .sort_values("ticker", kind="stable")
        .reset_index(drop=True)
    )
    return pos

def render_form_nova_operacao() -> None:
    st.subheader("➕ Nova operação")
    if st.session_state.msg:
        st.info(st.session_state.msg)

    with st.form("form_op", clear_on_submit=True):
        c1, c2 = st.columns(2)

        with c1:
            ticker = st.text_input("Ticker", placeholder="Ex: PETR4").strip().upper()
        with c2:
            operacao = st.selectbox("Operação", ["compra", "venda"])

        c3, c4, c5 = st.columns(3)
        with c3:
            preco = st.number_input("Preço (R$)", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        with c4:
            quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1)
        with c5:
            data_op = st.date_input("Data", value=date.today())
        submitted = st.form_submit_button("Registrar")

    if submitted:
        # validações simples

        if not ticker:
            st.error("Ticker é obrigatório.")
            return

        if not ticker.replace(".", "").isalnum():
            st.error("Ticker inválido (use letras/números; ex.: PETR4).")
            return

        row = pd.DataFrame([{
            "ticker": ticker,
            "operacao": operacao,
            "preco": float(preco),
            "quantidade": int(quantidade),
            "data": pd.to_datetime(data_op),
        }])
        row = ensure_schema(row)
        st.session_state.ops = pd.concat([st.session_state.ops, row], ignore_index=True)
        st.session_state.msg = f"Registrado: {ticker} ({operacao})."
        st.rerun() # reexecutar a aplicação streamlit

def init_state() -> None:
    if "ops" not in st.session_state:
        st.session_state.ops = new_empty_df() # operações
    if "msg" not in st.session_state:
        st.session_state.msg = "" # mensagens para o usuário

def main():
    st.set_page_config(page_title="Registro de Operações", layout="wide")
    st.title("📈 Registro de Operações de Compra/Venda")
    init_state() # inicializar variáveis
    render_sidebar_import_export()
    col_left, col_right = st.columns([1.2, 1])
    with col_left:
        render_form_nova_operacao()
    with col_right:
        render_posicao_carteira()
    st.divider()
    render_tabela_e_filtros()

if __name__ == "__main__":
    main()
