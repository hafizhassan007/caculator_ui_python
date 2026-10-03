import ast
import math
import operator
import re

import streamlit as st

st.set_page_config(page_title="Scientific Calculator", page_icon="🧮", layout="centered")

# ---------- Safe expression evaluator (no eval) ----------
BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
UN_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def fact(x):
    if x != int(x) or x < 0 or x > 170:
        raise ValueError("Factorial needs an integer between 0 and 170")
    return math.factorial(int(x))


def build_env(deg: bool, ans: float):
    to_rad = (lambda x: math.radians(x)) if deg else (lambda x: x)
    from_rad = (lambda x: math.degrees(x)) if deg else (lambda x: x)
    funcs = {
        "sin": lambda x: math.sin(to_rad(x)),
        "cos": lambda x: math.cos(to_rad(x)),
        "tan": lambda x: math.tan(to_rad(x)),
        "asin": lambda x: from_rad(math.asin(x)),
        "acos": lambda x: from_rad(math.acos(x)),
        "atan": lambda x: from_rad(math.atan(x)),
        "log": math.log10,
        "ln": math.log,
        "sqrt": math.sqrt,
        "abs": abs,
        "exp": math.exp,
        "fact": fact,
    }
    consts = {"pi": math.pi, "e": math.e, "ans": ans}
    return funcs, consts


def safe_eval(expr: str, deg: bool, ans: float):
    funcs, consts = build_env(deg, ans)
    # Preprocess: ^ -> **, implicit multiplication (2pi, 3(4+1), (2)(3), 2sin(x))
    s = expr.replace("^", "**")
    s = re.sub(r"(?<=[\d)])\s*(?=[a-zA-Z(])", "*", s)
    s = re.sub(r"\b(pi|e|ans)\b\s*(?=[\d(a-zA-Z])", r"\1*", s)
    s = re.sub(r"\)\s*(?=\d)", ")*", s)

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name) and n.id in consts:
            return consts[n.id]
        if isinstance(n, ast.UnaryOp) and type(n.op) in UN_OPS:
            return UN_OPS[type(n.op)](ev(n.operand))
        if isinstance(n, ast.BinOp) and type(n.op) in BIN_OPS:
            left, right = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Exponent too large")
            return BIN_OPS[type(n.op)](left, right)
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in funcs
            and not n.keywords
            and len(n.args) == 1
        ):
            return funcs[n.func.id](ev(n.args[0]))
        raise ValueError("Invalid expression")

    return ev(ast.parse(s, mode="eval"))


def fmt(x):
    if isinstance(x, complex):
        raise ValueError("Complex result")
    if isinstance(x, float) and abs(x) < 1e-12:
        x = 0.0
    return f"{x:.12g}"


# ---------- State ----------
st.session_state.setdefault("expr", "")
st.session_state.setdefault("ans", 0.0)
st.session_state.setdefault("msg", "")
st.session_state.setdefault("history", [])
st.session_state.setdefault("mode", "Deg")

INSERT = {
    "sin": "sin(", "cos": "cos(", "tan": "tan(",
    "asin": "asin(", "acos": "acos(", "atan": "atan(",
    "log": "log(", "ln": "ln(", "√": "sqrt(", "x²": "^2", "xʸ": "^",
    "π": "pi", "e": "e", "÷": "/", "×": "*", "−": "-", "n!": "fact(",
    "Ans": "ans", "1/x": "^(-1)", "abs": "abs(", "exp": "exp(",
}

# Streamlit renders button labels as Markdown, and a lone "+" is treated as a
# list bullet (so it shows up blank). Escaping it makes it display normally.
DISPLAY = {"+": "\\+"}


def press(label: str):
    st.session_state.msg = ""
    if label == "C":
        st.session_state.expr = ""
    elif label == "DEL":
        st.session_state.expr = st.session_state.expr[:-1]
    elif label == "=":
        expr = st.session_state.expr.strip()
        if not expr:
            return
        try:
            result = safe_eval(expr, st.session_state.mode == "Deg", st.session_state.ans)
            text = fmt(result)
            st.session_state.history.insert(0, f"{expr} = {text}")
            st.session_state.ans = float(result)
            st.session_state.expr = text
            st.session_state.msg = f"= {text}"
        except ZeroDivisionError:
            st.session_state.msg = "⚠️ Division by zero"
        except Exception as exc:
            st.session_state.msg = f"⚠️ {exc}" if str(exc) else "⚠️ Error"
    else:
        st.session_state.expr += INSERT.get(label, label)


# ---------- Styling ----------
st.markdown(
    """
    <style>
    .block-container {max-width: 520px; padding-top: 2rem;}
    div[data-testid="stTextInput"] input {
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-size: 1.6rem; text-align: right; padding: 0.8rem;
    }
    div.stButton > button {
        height: 3rem; font-size: 1.05rem; font-weight: 500; border-radius: 10px;
    }
    .result {text-align: right; font-size: 1.1rem; min-height: 1.6rem; opacity: .8;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- UI ----------
st.title("🧮 Scientific Calculator")

st.radio("Angle mode", ["Deg", "Rad"], horizontal=True, key="mode", label_visibility="collapsed")
st.text_input("Expression", key="expr", placeholder="0", label_visibility="collapsed")
st.markdown(f"<div class='result'>{st.session_state.msg}</div>", unsafe_allow_html=True)

ROWS = [
    ["sin", "cos", "tan", "(", ")"],
    ["asin", "acos", "atan", "π", "e"],
    ["log", "ln", "√", "x²", "xʸ"],
    ["abs", "exp", "1/x", "n!", "%"],
    ["7", "8", "9", "÷", "DEL"],
    ["4", "5", "6", "×", "C"],
    ["1", "2", "3", "−", "Ans"],
    ["0", ".", "+", "="],  # last row: 4 buttons, "=" is double width
]

for r, row in enumerate(ROWS):
    # Normal rows: 5 equal columns. Last row: "=" gets twice the width.
    cols = st.columns([1, 1, 1, 2] if len(row) == 4 else 5)
    for c, label in enumerate(row):
        cols[c].button(
            DISPLAY.get(label, label),
            key=f"btn_{r}_{c}",
            on_click=press,
            args=(label,),  # press() receives the original label, e.g. "+"
            use_container_width=True,
            type="primary" if label == "=" else "secondary",
        )

with st.expander("History"):
    if st.session_state.history:
        for item in st.session_state.history[:20]:
            st.code(item, language=None)
        if st.button("Clear history"):
            st.session_state.history = []
            st.rerun()
    else:
        st.caption("No calculations yet.")