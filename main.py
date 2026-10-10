import ast
import math
import operator
import html
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
st.session_state.setdefault("caret", None)      # insertion position (None = end)
st.session_state.setdefault("last_expr", "")    # expr jo hum ne last set kiya
st.session_state.setdefault("set_caret", None)  # JS ko cursor set karne ke liye
st.session_state.setdefault("nonce", 0)

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


# In buttons par "name()" insert hota hai aur cursor bracket ke andar rehta hai
FUNC_LABELS = {"sin", "cos", "tan", "asin", "acos", "atan", "log", "ln", "√", "n!", "abs", "exp"}


def press(label: str):
    ss = st.session_state
    ss.msg = ""
    expr = ss.expr

    # Agar user ne box mein khud type/edit kiya hai to purana caret bekaar hai -> end se continue
    if ss.caret is not None and expr == ss.last_expr:
        caret = min(ss.caret, len(expr))
    else:
        caret = len(expr)

    if label == "C":
        expr, caret = "", 0
    elif label == "⌫":
        if caret > 0:
            if expr[caret - 1] == "(" and expr[caret:caret + 1] == ")":
                expr = expr[:caret - 1] + expr[caret + 1:]  # "()" dono hatao
            else:
                expr = expr[:caret - 1] + expr[caret:]
            caret -= 1
    elif label == "=":
        stripped = expr.strip()
        if not stripped:
            return
        try:
            result = safe_eval(stripped, ss.mode == "Deg", ss.ans)
            text = fmt(result)
            ss.history.insert(0, f"{stripped} = {text}")
            ss.ans = float(result)
            expr, caret = text, len(text)
            ss.msg = f"= {text}"
        except ZeroDivisionError:
            ss.msg = "⚠️ Division by zero"
        except Exception as exc:
            ss.msg = f"⚠️ {exc}" if str(exc) else "⚠️ Error"
    elif label == ")" and expr[caret:caret + 1] == ")":
        caret += 1  # agle ")" ke upar se guzar jao
    else:
        base = INSERT.get(label, label)
        if label in FUNC_LABELS:
            ins, offset = base + ")", len(base)  # "cos(" + ")" , cursor "(" ke baad
        else:
            ins, offset = base, len(base)
        expr = expr[:caret] + ins + expr[caret:]
        caret += offset

    ss.expr = expr
    ss.last_expr = expr
    ss.caret = caret
    ss.set_caret = caret
    ss.nonce += 1


# ---------- Styling ----------
st.markdown(
    """
    <style>
    .block-container {max-width: 500px; padding-top: 1.5rem; padding-bottom: 3rem;}
    header[data-testid="stHeader"] {background: transparent;}

    .calc-title {font-size: clamp(1.3rem, 6.5vw, 2rem); white-space: nowrap; text-align: center; font-weight: 700; letter-spacing: .3px; margin: 0 0 .6rem 0; padding: 0;}

    /* Layout: buttons ke beech chhota gap, mobile par bhi ek row mein rahein */
    div[data-testid="stVerticalBlock"] {gap: .5rem;}
    div[data-testid="stHorizontalBlock"] {gap: .5rem; flex-wrap: nowrap !important;}
    div[data-testid="stColumn"] {min-width: 0 !important;}

    /* Display card */
    .st-key-display {
        background: linear-gradient(145deg, rgba(99,102,241,.14), rgba(139,92,246,.08));
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 18px; padding: .8rem 1rem .5rem 1rem;
        box-shadow: 0 4px 18px rgba(0,0,0,.12);
    }
    .st-key-display [data-testid="stTextInputRootElement"],
    .st-key-display [data-testid="stTextInputRootElement"]:focus-within,
    .st-key-display div[data-baseweb="input"],
    .st-key-display div[data-baseweb="base-input"] {
        background: transparent !important; border: none !important;
        box-shadow: none !important; outline: none !important;
    }
    .st-key-display input {
        font-family: ui-monospace, Menlo, Consolas, monospace;
        font-size: 2rem !important; text-align: right; padding: .3rem 0 !important;
        background: transparent !important;
    }
    .st-key-display input::placeholder {opacity: .35;}
    .result {text-align: right; font-size: 1rem; min-height: 1.5rem; opacity: .75; padding-bottom: .2rem;}

    /* Buttons: common */
    div.stButton > button {
        height: 3.1rem; font-size: 1.05rem; font-weight: 600; border-radius: 12px;
        border: 1px solid rgba(128,128,128,.25);
        transition: transform .08s ease, filter .15s ease, background .15s ease;
    }
    div.stButton > button p {font-size: inherit !important; font-weight: inherit !important; margin: 0;}
    div.stButton > button:hover {filter: brightness(1.15); transform: translateY(-1px);}
    div.stButton > button:active {transform: translateY(1px) scale(.97);}

    /* Categories (key prefix se pehchan) */
    [class*="st-key-fn_"] div.stButton > button {background: rgba(99,102,241,.12);  border-color: rgba(99,102,241,.30); font-size: .95rem;}
    [class*="st-key-num_"] div.stButton > button {background: rgba(128,128,128,.14); font-size: 1.15rem;}
    [class*="st-key-op_"] div.stButton > button {background: rgba(245,158,11,.20);  border-color: rgba(245,158,11,.45); font-size: 1.25rem;}
    [class*="st-key-act_"] div.stButton > button {background: rgba(239,68,68,.18);   border-color: rgba(239,68,68,.40);}
    [class*="st-key-eq_"] div.stButton > button {
        background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; border: none;
        font-size: 1.4rem; box-shadow: 0 4px 14px rgba(99,102,241,.45);
    }

    /* History / shortcuts */
    div[data-testid="stExpander"] {border-radius: 14px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- UI ----------
st.markdown("<u><h4 class='calc-title'>By Hassan Ahmad</h4></u>", unsafe_allow_html=True)
st.markdown("<h2 class='calc-title'>🧮 Scientific Calculator </h2>", unsafe_allow_html=True)

try:
    display = st.container(key="display")
except TypeError:  # purana Streamlit
    display = st.container()

with display:
    st.radio("Angle mode", ["Deg", "Rad"], horizontal=True, key="mode", label_visibility="collapsed")
    st.text_input("Expression", key="expr", placeholder="0", label_visibility="collapsed")
    st.markdown(
        f"<div class='result'>{html.escape(st.session_state.msg) or '&nbsp;'}</div>",
        unsafe_allow_html=True,
    )

ROWS = [
    ["sin", "cos", "tan", "(", ")"],
    ["asin", "acos", "atan", "π", "e"],
    ["log", "ln", "√", "x²", "xʸ"],
    ["abs", "exp", "1/x", "n!", "%"],
    ["7", "8", "9", "÷", "⌫"],
    ["4", "5", "6", "×", "C"],
    ["1", "2", "3", "−", "Ans"],
    ["0", ".", "+", "="],  # last row: 4 buttons, "=" is double width
]


def kind_of(label: str) -> str:
    if label == "=":
        return "eq"
    if label in ("⌫", "C"):
        return "act"
    if label in ("÷", "×", "−", "+"):
        return "op"
    if label.isdigit() or label == ".":
        return "num"
    return "fn"


for r, row in enumerate(ROWS):
    # Normal rows: 5 equal columns. Last row: "=" gets twice the width.
    cols = st.columns([1, 1, 1, 2] if len(row) == 4 else 5)
    for c, label in enumerate(row):
        cols[c].button(
            DISPLAY.get(label, label),
            key=f"{kind_of(label)}_{r}_{c}",
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

with st.expander("⌨️ Keyboard shortcuts"):
    st.markdown(
        """
| Key | Action |
|---|---|
| `0-9` `.` `( )` `+ - * /` `^` `!` `%` | Number / operator |
| `Enter` | Calculate (`=`) |
| `Backspace` | ⌫ (ek character hatao) |
| `Delete` ya `Esc` | **C** (sab clear) |
| `p` `e` `r` `a` | π, e, √, Ans |
| `s` `c` `t` `l` `n` | sin, cos, tan, log, ln |

Box ke andar letters normal type hote hain; shortcuts tab chalte hain jab cursor box ke bahar ho.
`Enter`, `Delete` aur `Esc` box ke andar bhi kaam karte hain.
"""
    )

# ---------- Keyboard support ----------
KEY_JS = """
    <script>
    const doc = window.parent.document;

    // Purana listener hatao (har rerun par duplicate na ho)
    if (window.parent.__calcKeyHandler) {
        doc.removeEventListener("keydown", window.parent.__calcKeyHandler, true);
    }

    const KEYMAP = {
        "+": "+", "-": "−", "*": "×", "x": "×", "X": "×", "/": "÷",
        "^": "xʸ", "(": "(", ")": ")", ".": ".", "%": "%", "!": "n!",
        "p": "π", "e": "e", "r": "√", "a": "Ans",
        "s": "sin", "c": "cos", "t": "tan", "l": "log", "n": "ln",
        "Backspace": "⌫", "Delete": "C", "Escape": "C",
        "Enter": "=", "=": "="
    };
    for (let i = 0; i <= 9; i++) KEYMAP[String(i)] = String(i);

    function clickButton(label) {
        const btns = doc.querySelectorAll("button");
        for (const b of btns) {
            if (b.textContent.trim() === label) { b.click(); return true; }
        }
        return false;
    }

    const handler = function (e) {
        if (e.ctrlKey || e.metaKey || e.altKey) return;

        const inInput = e.target.closest && e.target.closest('[data-testid="stTextInput"]');

        if (inInput) {
            // Expression box mein normal typing chalne do.
            // Enter = evaluate, Delete / Escape = C (clear).
            // Backspace box mein normal chalta hai (cursor ke peeche ka character hatata hai).
            if (e.key === "Enter" || e.key === "Escape" || e.key === "Delete") {
                e.preventDefault();
                e.stopPropagation();
                e.target.blur();  // value Streamlit mein commit ho jaye
                const label = e.key === "Enter" ? "=" : "C";
                setTimeout(() => clickButton(label), 120);
            }
            return;
        }

        // Radio / koi aur input ho to ignore
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

        const label = KEYMAP[e.key];
        if (label && clickButton(label)) {
            e.preventDefault();  // focused button par double-click na ho
        }
    };

    window.parent.__calcKeyHandler = handler;
    doc.addEventListener("keydown", handler, true);
    </script>
    """

# Naye Streamlit mein st.iframe hai (components.html deprecated ho chuka hai)
if hasattr(st, "iframe"):
    st.iframe(KEY_JS, height=1)
else:
    import streamlit.components.v1 as components
    components.html(KEY_JS, height=0)


# ---------- Button dabane ke baad input mein focus + cursor sahi jagah ----------
if st.session_state.set_caret is not None:
    pos = int(st.session_state.set_caret)
    nonce = st.session_state.nonce
    CARET_JS = f"""
    <script>
    // run {nonce}
    setTimeout(function () {{
        const el = window.parent.document.querySelector('[data-testid="stTextInput"] input');
        if (el) {{ el.focus(); el.setSelectionRange({pos}, {pos}); }}
    }}, 60);
    </script>
    """
    if hasattr(st, "iframe"):
        st.iframe(CARET_JS, height=1)
    else:
        import streamlit.components.v1 as components
        components.html(CARET_JS, height=0)
    st.session_state.set_caret = None