(() => {
  "use strict";

  const log = document.getElementById("log");
  const form = document.getElementById("composer");
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("send");
  const chips = document.getElementById("chips");

  let context = null; // echoed back to the server so it can follow the conversation
  let busy = false;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function scrollDown() {
    window.scrollTo({ top: document.body.scrollHeight });
  }

  function addUser(text) {
    const li = el("li", "msg user");
    li.appendChild(el("div", "text", text));
    log.appendChild(li);
    scrollDown();
  }

  function addBot(text, data) {
    const li = el("li", "msg bot");
    li.appendChild(el("div", "who", "Aurelius"));
    li.appendChild(el("div", "text", text));
    if (data && data.type === "conversion") li.appendChild(buildSlip(data));
    if (data && data.type === "currencies") li.appendChild(buildRegister(data.items));
    log.appendChild(li);
    scrollDown();
    return li;
  }

  function buildSlip(data) {
    const slip = el("div", "slip");
    if (data.status !== "live") {
      slip.appendChild(el("div", "stamp", data.status === "offline" ? "Offline estimate" : "Last known rates"));
    }
    const from = el("div", "slip-from");
    from.append("Converting ", el("strong", "", `${data.amount_fmt} ${data.source.code}`));
    from.appendChild(el("div", "slip-name", data.source.name));
    slip.appendChild(from);

    data.results.forEach((r) => {
      const row = el("div", "slip-row");
      const value = el("div", "slip-value", r.value_fmt);
      value.appendChild(el("small", "", r.code));
      row.appendChild(value);
      row.appendChild(el("div", "slip-name", r.name));
      row.appendChild(el("div", "slip-rate", r.rate_fmt));
      slip.appendChild(row);
    });

    const when = new Date(data.as_of);
    const stamp = isNaN(when) ? "" : ` · ${when.toLocaleString()}`;
    slip.appendChild(el("div", "slip-foot", `Source: ${data.provider}${stamp}`));
    return slip;
  }

  function buildRegister(items) {
    const wrap = el("div", "register");
    const table = el("table");
    items.forEach((c) => {
      const tr = el("tr");
      tr.appendChild(el("td", "", c.code));
      tr.appendChild(el("td", "", c.name));
      table.appendChild(tr);
    });
    wrap.appendChild(table);
    return wrap;
  }

  function addTyping() {
    const li = el("li", "msg bot");
    li.appendChild(el("div", "who", "Aurelius"));
    const dots = el("div", "typing");
    dots.setAttribute("aria-label", "Aurelius is composing a reply");
    dots.append(el("span"), el("span"), el("span"));
    li.appendChild(dots);
    log.appendChild(li);
    scrollDown();
    return li;
  }

  async function send(message) {
    message = message.trim();
    if (!message || busy) return;
    busy = true;
    sendBtn.disabled = true;
    input.value = "";
    addUser(message);
    const typing = addTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, context }),
      });
      const body = await res.json();
      typing.remove();
      if (body.context !== undefined && body.context !== null) context = body.context;
      addBot(body.reply || "Something went wrong on my end. Try again.", body.data);
    } catch (err) {
      typing.remove();
      addBot("I can't reach my own server. Check that the app is still running in your terminal, then try again.");
    } finally {
      busy = false;
      sendBtn.disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    send(input.value);
  });

  chips.addEventListener("click", (e) => {
    if (e.target.classList.contains("chip")) send(e.target.textContent);
  });

  addBot("I am Aurelius. Give me an amount and two currencies, and I shall perform the conversion that lesser minds find difficult. Type \"help\" if you must.");
})();
