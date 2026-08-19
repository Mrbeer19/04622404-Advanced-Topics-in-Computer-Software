/* RAG AI Assistant — ฝั่งหน้าเว็บ
   คุยกับ backend เดิมของโปรเจกต์ผ่าน /api/ask เท่านั้น
   ไม่มีการเรียก LLM หรือถือ API key ใด ๆ ในเบราว์เซอร์ */

(function () {
  "use strict";

  var API_TIMEOUT_MS = 180000;              // LLM บนเครื่องอาจใช้เวลาหลายสิบวินาที
  var STORE_MSGS = "rag_chat_messages";
  var STORE_SID = "rag_chat_session";

  var el = {
    chat: document.getElementById("chat"),
    empty: document.getElementById("empty-state"),
    form: document.getElementById("form"),
    input: document.getElementById("input"),
    send: document.getElementById("btn-send"),
    clear: document.getElementById("btn-clear"),
    counter: document.getElementById("counter"),
    status: document.getElementById("status"),
    statusText: document.getElementById("status-text"),
    botImg: document.getElementById("ai-bot-img")
  };

  var messages = [];        // [{ role: "user" | "ai" | "error", text, sources, elapsed, time }]
  var isLoading = false;    // กันการส่งซ้ำระหว่างรอคำตอบ
  var sessionId = "";

  /* ---------------------------------------------------------- utilities */

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ทำเลขอ้างอิง [1] [2] ให้เด่นขึ้น (escape ก่อนเสมอ)
  function formatAnswer(textValue) {
    return escapeHtml(textValue).replace(/\[(\d+)\]/g, '<span class="cite">[$1]</span>');
  }

  function now() {
    return new Date().toLocaleTimeString("th-TH", { hour: "2-digit", minute: "2-digit" });
  }

  function newSessionId() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "s-" + Date.now() + "-" + Math.random().toString(16).slice(2);
  }

  function scrollToBottom() {
    requestAnimationFrame(function () {
      el.chat.scrollTop = el.chat.scrollHeight;
    });
  }

  /* ---------------------------------------------------------- storage */

  function loadState() {
    try {
      sessionId = localStorage.getItem(STORE_SID) || "";
      if (!sessionId) {
        sessionId = newSessionId();
        localStorage.setItem(STORE_SID, sessionId);
      }
      var saved = JSON.parse(localStorage.getItem(STORE_MSGS) || "[]");
      messages = Array.isArray(saved) ? saved : [];
    } catch (error) {
      // localStorage ถูกปิด หรือข้อมูลเสีย — ใช้งานต่อได้แบบไม่จำประวัติ
      sessionId = newSessionId();
      messages = [];
    }
  }

  function saveState() {
    try {
      localStorage.setItem(STORE_MSGS, JSON.stringify(messages));
    } catch (error) {
      /* เต็มหรือถูกปิดอยู่ — ข้ามไป ไม่ให้กระทบการใช้งาน */
    }
  }

  /* ---------------------------------------------------------- rendering */

  // ป้ายใต้คำตอบ: ใครเป็นคนตอบ ตอบจากอะไร และใช้เวลาไปเท่าไร
  function sourceTags(message) {
    var model = escapeHtml(message.model || "โมเดล");
    var count = (message.sources && message.sources.length) || 0;

    switch (message.answeredBy) {
      case "llm":
        return tag("ok", "เขียนคำตอบโดย " + model) +
               tag("", "อ้างอิงฐานความรู้ " + count + " รายการ");
      case "llm_refused":
        return tag("warn", "ไม่พบข้อมูลที่ตอบคำถามนี้ในฐานความรู้") +
               tag("", model + " เลือกไม่เดาคำตอบ · ค้นมาให้ " + count + " รายการ");
      case "no_context":
        return tag("warn", "ค้นไม่พบเอกสารที่เกี่ยวข้อง") +
               tag("", "ระบบตอบว่าไม่รู้ ไม่ได้ส่งให้ " + model + " เดา");
      case "fallback_context":
        return tag("warn", "เรียก " + model + " ไม่สำเร็จ") +
               tag("", "ข้อความนี้มาจากฐานความรู้โดยตรง ไม่ได้ผ่านการเรียบเรียง");
      case "no_llm":
        return tag("", "โหมดไม่ใช้ LLM · ข้อความจากฐานความรู้โดยตรง");
      default:
        return count ? tag("", "อ้างอิงฐานความรู้ " + count + " รายการ") : "";
    }
  }

  function timeTag(message) {
    if (!message.elapsed) return "";

    var timings = message.timings || {};
    var steps = [];
    if (timings["ค้นหา"] != null) steps.push("ค้นหา " + timings["ค้นหา"] + " วิ");
    if (timings["เขียนคำตอบ"] != null) steps.push("เขียนคำตอบ " + timings["เขียนคำตอบ"] + " วิ");

    return tag("", "ใช้เวลา " + message.elapsed + " วินาที" +
                   (steps.length ? " (" + steps.join(" · ") + ")" : ""));
  }

  function tag(kind, text) {
    return '<span class="tag' + (kind ? " tag--" + kind : "") + '">' + escapeHtml(text) + "</span>";
  }

  function messageNode(message, index) {
    var wrap = document.createElement("div");
    var isUser = message.role === "user";
    var isError = message.role === "error";

    wrap.className = "msg " + (isUser ? "msg--user" : isError ? "msg--error" : "msg--ai");

    var who = isUser ? "คุณ" : isError ? "ระบบ" : "AI Assistant";
    var avatar = isUser ? "คุณ" : isError ? "!" : "AI";

    var html =
      '<div class="msg__avatar" aria-hidden="true">' + escapeHtml(avatar) + "</div>" +
      '<div class="msg__body">' +
        '<div class="msg__who">' + escapeHtml(who) + "</div>" +
        '<div class="msg__bubble">' +
          (isUser || isError ? escapeHtml(message.text) : formatAnswer(message.text)) +
        "</div>";

    // ที่มาของคำตอบ + เวลาที่ใช้
    if (!isUser && !isError) {
      var tags = sourceTags(message) + timeTag(message);
      if (tags) html += '<div class="msg__meta">' + tags + "</div>";
    }

    // แหล่งอ้างอิงของคำตอบ
    if (!isUser && !isError && message.sources && message.sources.length) {
      html += '<details class="sources"><summary>แหล่งอ้างอิง ' +
              message.sources.length + " รายการ</summary><ol>";
      message.sources.forEach(function (source) {
        html += "<li>" + escapeHtml(source.question || "-") +
                '<div class="src-meta">บรรทัด ' + escapeHtml(source.line_no) +
                " · คะแนน " + escapeHtml(source.score) + "</div></li>";
      });
      html += "</ol></details>";
    }

    // ปุ่ม Copy + เวลา
    html += '<div class="msg__tools">';
    if (!isUser) {
      html += '<button class="tool-btn" type="button" data-copy="' + index + '">คัดลอกคำตอบ</button>';
    }
    html += '<span class="msg__time">' + escapeHtml(message.time || "") + "</span>";
    html += "</div></div>";

    wrap.innerHTML = html;
    return wrap;
  }

  function render() {
    // ล้างเฉพาะข้อความ ไม่แตะหน้าจอเริ่มต้น
    Array.prototype.slice.call(el.chat.querySelectorAll(".msg, .msg-loading"))
      .forEach(function (node) { node.remove(); });

    el.empty.style.display = messages.length ? "none" : "";

    messages.forEach(function (message, index) {
      el.chat.appendChild(messageNode(message, index));
    });

    if (isLoading) el.chat.appendChild(loadingNode());
    scrollToBottom();
  }

  function loadingNode() {
    var wrap = document.createElement("div");
    wrap.className = "msg msg--ai msg-loading";
    wrap.innerHTML =
      '<div class="msg__avatar" aria-hidden="true">AI</div>' +
      '<div class="msg__body">' +
        '<div class="msg__who">AI Assistant</div>' +
        '<div class="msg__bubble"><span class="typing">' +
          '<span class="typing-dots"><i></i><i></i><i></i></span>' +
          "AI กำลังค้นหาข้อมูลและสร้างคำตอบ..." +
        "</span></div>" +
      "</div>";
    return wrap;
  }

  function push(role, text, extra) {
    var message = { role: role, text: text, time: now() };
    if (extra) {
      if (extra.sources) message.sources = extra.sources;
      if (extra.elapsed) message.elapsed = extra.elapsed;
      if (extra.timings) message.timings = extra.timings;
      if (extra.answeredBy) message.answeredBy = extra.answeredBy;
      if (extra.model) message.model = extra.model;
    }
    messages.push(message);
    saveState();
    render();
  }

  /* ---------------------------------------------------------- loading state */

  function setLoading(value) {
    isLoading = value;
    el.send.disabled = value;
    el.input.disabled = value;
    el.send.classList.toggle("is-loading", value);
    el.send.querySelector(".btn-label").textContent = value ? "กำลังตอบ..." : "ส่งคำถาม";
    
    // Toggle AI bot animation classes
    if (el.botImg) {
      if (value) {
        el.botImg.classList.remove("bot-idle");
        el.botImg.classList.add("bot-talking");
      } else {
        el.botImg.classList.remove("bot-talking");
        el.botImg.classList.add("bot-idle");
      }
    }

    if (!value) el.input.focus();
  }

  /* ---------------------------------------------------------- API call */

  function askApi(question) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, API_TIMEOUT_MS);

    return fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, session_id: sessionId }),
      signal: controller.signal
    })
      .catch(function (error) {
        // แยกให้ชัดว่าเป็นเรื่อง "ต่อ API ไม่ได้" หรือ "รอนานเกินไป"
        if (error && error.name === "AbortError") {
          throw new Error("AI ไม่ตอบกลับภายในเวลาที่กำหนด — โมเดลอาจกำลังทำงานหนัก กรุณาลองใหม่อีกครั้ง");
        }
        throw new Error("เชื่อมต่อกับเซิร์ฟเวอร์ไม่ได้ — ตรวจสอบว่ารัน python api.py อยู่หรือไม่");
      })
      .then(function (response) {
        return response.text().then(function (raw) {
          var data = null;
          try {
            data = JSON.parse(raw);
          } catch (error) {
            // ตอบกลับมาแต่ไม่ใช่ JSON
            throw new Error("รูปแบบข้อมูลที่ได้รับจากเซิร์ฟเวอร์ไม่ถูกต้อง");
          }

          if (!response.ok) {
            var serverMessage = data && typeof data.error === "string" ? data.error : "";
            if (response.status >= 500 && !serverMessage) {
              serverMessage = "เซิร์ฟเวอร์เกิดข้อผิดพลาด (" + response.status + ")";
            }
            throw new Error(serverMessage || "เกิดข้อผิดพลาด (" + response.status + ")");
          }

          // ตรวจรูปแบบ response ก่อนเอาไปแสดง
          if (!data || typeof data.answer !== "string" || !data.answer.trim()) {
            throw new Error("AI ไม่ได้ตอบกลับ หรือรูปแบบคำตอบไม่ถูกต้อง");
          }
          if (data.sources && !Array.isArray(data.sources)) data.sources = [];

          return data;
        });
      })
      .finally(function () { clearTimeout(timer); });
  }

  /* ---------------------------------------------------------- actions */

  function send() {
    if (isLoading) return;                       // ป้องกันการส่งซ้ำขณะกำลังโหลด

    var question = el.input.value.trim();
    if (!question) {                             // คำถามว่าง
      el.input.focus();
      el.input.classList.add("shake");
      push("error", "กรุณาพิมพ์คำถามก่อนกดส่ง");
      setTimeout(function () { el.input.classList.remove("shake"); }, 400);
      return;
    }

    push("user", question);
    el.input.value = "";
    autosize();
    updateCounter();
    setLoading(true);
    render();

    askApi(question)
      .then(function (data) {
        if (data.session_id) {
          sessionId = data.session_id;
          try { localStorage.setItem(STORE_SID, sessionId); } catch (error) { /* ไม่สำคัญ */ }
        }
        setLoading(false);
        push("ai", data.answer, {
          sources: data.sources,
          elapsed: data.elapsed,
          timings: data.timings,
          answeredBy: data.answered_by,
          model: data.model
        });
      })
      .catch(function (error) {
        setLoading(false);
        push("error", error && error.message ? error.message : "เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ");
      });
  }

  function clearHistory() {
    if (messages.length && !window.confirm("ล้างประวัติการสนทนาทั้งหมดใช่หรือไม่")) return;

    messages = [];
    saveState();
    render();

    // ล้างความจำฝั่ง server ด้วย เพื่อไม่ให้คำถามถัดไปอ้างอิงบทสนทนาเก่า
    fetch("/api/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId })
    }).catch(function () { /* ล้างฝั่งหน้าเว็บสำเร็จแล้ว ถือว่าพอ */ });
  }

  function copyAnswer(index, button) {
    var message = messages[index];
    if (!message) return;

    var done = function () {
      var original = button.textContent;
      button.textContent = "คัดลอกแล้ว";
      button.classList.add("is-done");
      setTimeout(function () {
        button.textContent = original;
        button.classList.remove("is-done");
      }, 1600);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(message.text).then(done, fallbackCopy);
    } else {
      fallbackCopy();
    }

    function fallbackCopy() {
      // สำหรับเบราว์เซอร์เก่า หรือหน้าเว็บที่ไม่ได้เปิดผ่าน https
      var area = document.createElement("textarea");
      area.value = message.text;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy"); done(); } catch (error) { /* ไม่รองรับ */ }
      document.body.removeChild(area);
    }
  }

  /* ---------------------------------------------------------- input helpers */

  function autosize() {
    el.input.style.height = "auto";
    el.input.style.height = Math.min(el.input.scrollHeight, 168) + "px";
  }

  function updateCounter() {
    el.counter.textContent = el.input.value.length + " / 1000";
  }

  /* ---------------------------------------------------------- health */

  function checkHealth() {
    fetch("/api/health")
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data && data.ready) {
          el.status.className = "status status--ok";
          el.statusText.textContent = "พร้อมใช้งาน · " + (data.model || "");
        } else {
          el.status.className = "status status--down";
          el.statusText.textContent = "ระบบยังไม่พร้อม";
          push("error", (data && data.error) || "ระบบยังไม่พร้อมใช้งาน");
        }
      })
      .catch(function () {
        el.status.className = "status status--down";
        el.statusText.textContent = "เชื่อมต่อไม่ได้";
      });
  }

  /* ---------------------------------------------------------- events */

  el.form.addEventListener("submit", function (event) {
    event.preventDefault();
    send();
  });

  // Enter = ส่ง, Shift + Enter = ขึ้นบรรทัดใหม่
  el.input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      send();
    }
  });

  el.input.addEventListener("input", function () {
    autosize();
    updateCounter();
  });

  el.clear.addEventListener("click", clearHistory);

  // ปุ่มคัดลอก และคำถามตัวอย่าง
  document.addEventListener("click", function (event) {
    var copyBtn = event.target.closest("[data-copy]");
    if (copyBtn) {
      copyAnswer(Number(copyBtn.getAttribute("data-copy")), copyBtn);
      return;
    }

    var chip = event.target.closest(".chip");
    if (chip && !isLoading) {
      el.input.value = chip.textContent.trim();
      autosize();
      updateCounter();
      send();
    }
  });

  /* ---------------------------------------------------------- start */

  loadState();
  render();
  updateCounter();
  checkHealth();
  el.input.focus();
})();
