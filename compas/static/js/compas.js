/*
 * compas.js — a tiny, dependency-free HTMX-style helper.
 *
 * CDNs are intentionally not used (Compas is local-first), so this vendored
 * script implements the small subset of HTMX behaviour the dashboard relies
 * on: hx-get / hx-post, hx-target, hx-swap, hx-trigger (with `changed` and
 * `delay:Nms` modifiers), hx-push-url, hx-include and hx-indicator. Every
 * request sends the `HX-Request: true` header so the server returns partials.
 */
(function () {
  "use strict";

  function qsa(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function resolveTarget(el) {
    var t = el.getAttribute("hx-target");
    if (!t || t === "this") return el;
    if (t.indexOf("closest ") === 0) return el.closest(t.slice(8).trim());
    if (t.indexOf("find ") === 0) return el.querySelector(t.slice(5).trim());
    return document.querySelector(t);
  }

  function swap(target, html, mode) {
    mode = mode || "innerHTML";
    if (mode === "outerHTML") {
      var tmp = document.createElement("div");
      tmp.innerHTML = html;
      var nodes = Array.prototype.slice.call(tmp.childNodes);
      var parent = target.parentNode;
      nodes.forEach(function (n) { parent.insertBefore(n, target); });
      parent.removeChild(target);
      nodes.forEach(function (n) { if (n.nodeType === 1) process(n); });
      return;
    }
    if (mode === "beforeend") { target.insertAdjacentHTML("beforeend", html); }
    else if (mode === "afterbegin") { target.insertAdjacentHTML("afterbegin", html); }
    else { target.innerHTML = html; }
    process(target);
  }

  function collectParams(el) {
    var params = new URLSearchParams();
    var form = el.tagName === "FORM" ? el : el.closest("form");
    if (form) {
      new FormData(form).forEach(function (v, k) { params.append(k, v); });
    }
    var include = el.getAttribute("hx-include");
    if (include) {
      qsa(include).forEach(function (inp) {
        if (inp.name) params.append(inp.name, inp.value);
      });
    }
    var vals = el.getAttribute("hx-vals");
    if (vals) {
      try { var obj = JSON.parse(vals); Object.keys(obj).forEach(function (k) { params.set(k, obj[k]); }); }
      catch (e) {}
    }
    return params;
  }

  function indicator(el, on) {
    var sel = el.getAttribute("hx-indicator");
    var node = sel ? document.querySelector(sel) : el;
    if (node) node.classList.toggle("htmx-loading", on);
    document.body.classList.toggle("compas-busy", on);
  }

  function request(el, evt) {
    if (evt) evt.preventDefault();
    var method = el.getAttribute("hx-get") ? "GET" : "POST";
    var url = el.getAttribute("hx-get") || el.getAttribute("hx-post");
    var target = resolveTarget(el);
    if (!target) { console.warn("compas: no target for", el); return; }
    var params = collectParams(el);
    var opts = { method: method, headers: { "HX-Request": "true" } };

    if (method === "GET") {
      var q = params.toString();
      if (q) url += (url.indexOf("?") === -1 ? "?" : "&") + q;
    } else {
      opts.headers["Content-Type"] = "application/x-www-form-urlencoded";
      opts.body = params.toString();
    }

    indicator(el, true);
    fetch(url, opts)
      .then(function (r) { return r.text().then(function (t) { return { ok: r.ok, text: t, url: r.url }; }); })
      .then(function (res) {
        swap(target, res.text, el.getAttribute("hx-swap"));
        if (el.getAttribute("hx-push-url") === "true") {
          try { history.pushState({}, "", url); } catch (e) {}
        }
        document.dispatchEvent(new CustomEvent("compas:afterSwap", { detail: { target: target, el: el } }));
      })
      .catch(function (err) { console.error("compas request failed", err); })
      .finally(function () { indicator(el, false); });
  }

  function parseTriggers(el) {
    var raw = el.getAttribute("hx-trigger");
    if (!raw) {
      if (el.tagName === "FORM") return [{ event: "submit" }];
      if (el.tagName === "INPUT" || el.tagName === "SELECT") return [{ event: "change" }];
      return [{ event: "click" }];
    }
    return raw.split(",").map(function (part) {
      var tokens = part.trim().split(/\s+/);
      var spec = { event: tokens[0], changed: false, delay: 0 };
      tokens.slice(1).forEach(function (tok) {
        if (tok === "changed") spec.changed = true;
        else if (tok.indexOf("delay:") === 0) spec.delay = parseInt(tok.slice(6), 10) || 0;
      });
      return spec;
    });
  }

  function bind(el) {
    if (el.__compasBound) return;
    el.__compasBound = true;
    parseTriggers(el).forEach(function (spec) {
      var timer = null;
      var last = null;
      el.addEventListener(spec.event, function (evt) {
        if (spec.changed) {
          var v = (evt.target && "value" in evt.target) ? evt.target.value : null;
          if (v === last) return;
          last = v;
        }
        if (spec.event === "submit") evt.preventDefault();
        if (spec.delay) {
          clearTimeout(timer);
          timer = setTimeout(function () { request(el, null); }, spec.delay);
        } else {
          request(el, evt);
        }
      });
      if (spec.event === "load") request(el, null);
    });
  }

  function process(root) {
    qsa("[hx-get],[hx-post]", root).forEach(bind);
    if (root.nodeType === 1 && (root.hasAttribute("hx-get") || root.hasAttribute("hx-post"))) bind(root);
  }

  // Public helper used by the graph explorer + assistant drawer.
  window.compas = {
    process: process,
    fetchJSON: function (url) {
      return fetch(url, { headers: { "HX-Request": "true" } }).then(function (r) { return r.json(); });
    },
    postForm: function (url, target, data) {
      var body = new URLSearchParams(data).toString();
      return fetch(url, {
        method: "POST",
        headers: { "HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded" },
        body: body
      }).then(function (r) { return r.text(); }).then(function (t) {
        if (target) swap(target, t, "innerHTML");
        return t;
      });
    }
  };

  document.addEventListener("DOMContentLoaded", function () { process(document); });
})();
