/*
 * graph.js — a small SVG force-directed graph for the Graph Explorer.
 *
 * Vendored (no Cytoscape/D3 CDN, keeping Compas local-first) but covers the
 * required interactions: zoom, pan, drag, expand/collapse a node, search,
 * highlight a path and inspect a node's details/evidence. It consumes the
 * Cytoscape-style payloads returned by /api/graph.
 */
(function () {
  "use strict";

  var SVGNS = "http://www.w3.org/2000/svg";
  var TYPE_COLORS = {
    Capability: "#6366f1", Technology: "#0ea5e9", Platform: "#06b6d4",
    Team: "#22c55e", Decision: "#f59e0b", Risk: "#ef4444", Process: "#a855f7",
    Initiative: "#ec4899", Product: "#14b8a6", Concept: "#94a3b8"
  };

  function GraphView(container, opts) {
    this.container = container;
    this.opts = opts || {};
    this.nodes = {};   // id -> node {id,label,type,x,y,vx,vy,fixed}
    this.edges = [];   // {source,target,label,confidence}
    this.scale = 1;
    this.tx = 0; this.ty = 0;
    this.selected = null;
    this.highlightPath = [];
    this._build();
  }

  GraphView.prototype._build = function () {
    var svg = document.createElementNS(SVGNS, "svg");
    svg.setAttribute("class", "graph-svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    var root = document.createElementNS(SVGNS, "g");
    this.edgeLayer = document.createElementNS(SVGNS, "g");
    this.nodeLayer = document.createElementNS(SVGNS, "g");
    root.appendChild(this.edgeLayer);
    root.appendChild(this.nodeLayer);
    svg.appendChild(root);
    this.svg = svg; this.root = root;
    this.container.innerHTML = "";
    this.container.appendChild(svg);
    this._bindPanZoom();
  };

  GraphView.prototype._bindPanZoom = function () {
    var self = this, panning = false, sx = 0, sy = 0;
    this.svg.addEventListener("mousedown", function (e) {
      if (e.target.closest(".graph-node")) return;
      panning = true; sx = e.clientX - self.tx; sy = e.clientY - self.ty;
    });
    window.addEventListener("mousemove", function (e) {
      if (!panning) return;
      self.tx = e.clientX - sx; self.ty = e.clientY - sy; self._applyTransform();
    });
    window.addEventListener("mouseup", function () { panning = false; });
    this.svg.addEventListener("wheel", function (e) {
      e.preventDefault();
      var f = e.deltaY < 0 ? 1.1 : 0.9;
      self.scale = Math.max(0.2, Math.min(3, self.scale * f));
      self._applyTransform();
    }, { passive: false });
  };

  GraphView.prototype._applyTransform = function () {
    this.root.setAttribute("transform",
      "translate(" + this.tx + "," + this.ty + ") scale(" + this.scale + ")");
  };

  GraphView.prototype.setData = function (payload, opts) {
    opts = opts || {};
    var w = this.container.clientWidth || 800, h = this.container.clientHeight || 600;
    if (!opts.merge) { this.nodes = {}; this.edges = []; }
    var self = this;
    payload.nodes.forEach(function (n) {
      var d = n.data;
      if (!self.nodes[d.id]) {
        self.nodes[d.id] = {
          id: d.id, label: d.label, type: d.type, status: d.status,
          confidence: d.confidence, evidence: d.evidence_count,
          x: w / 2 + (Math.random() - 0.5) * w * 0.6,
          y: h / 2 + (Math.random() - 0.5) * h * 0.6,
          vx: 0, vy: 0, focus: d.focus
        };
      }
    });
    payload.edges.forEach(function (e) {
      var d = e.data;
      if (self.nodes[d.source] && self.nodes[d.target] &&
          !self.edges.some(function (x) { return x.id === d.id; })) {
        self.edges.push({ id: d.id, source: d.source, target: d.target,
          label: d.label, confidence: d.confidence, review: d.review_status });
      }
    });
    this._layout();
    this.render();
  };

  GraphView.prototype._layout = function () {
    var ids = Object.keys(this.nodes);
    var w = this.container.clientWidth || 800, h = this.container.clientHeight || 600;
    var k = Math.sqrt((w * h) / Math.max(1, ids.length)) * 0.7;
    for (var iter = 0; iter < 220; iter++) {
      for (var i = 0; i < ids.length; i++) {
        var a = this.nodes[ids[i]]; a.vx = 0; a.vy = 0;
        for (var j = 0; j < ids.length; j++) {
          if (i === j) continue;
          var b = this.nodes[ids[j]];
          var dx = a.x - b.x, dy = a.y - b.y;
          var dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
          var rep = (k * k) / dist;
          a.vx += (dx / dist) * rep; a.vy += (dy / dist) * rep;
        }
      }
      this.edges.forEach(function (e) {
        var a = this.nodes[e.source], b = this.nodes[e.target];
        if (!a || !b) return;
        var dx = b.x - a.x, dy = b.y - a.y;
        var dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
        var att = (dist * dist) / k;
        var fx = (dx / dist) * att, fy = (dy / dist) * att;
        a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
      }, this);
      var temp = 0.85 * (1 - iter / 220) * k * 0.1 + 1;
      for (var m = 0; m < ids.length; m++) {
        var n = this.nodes[ids[m]];
        if (n.fixed) continue;
        var sp = Math.sqrt(n.vx * n.vx + n.vy * n.vy) || 0.01;
        n.x += (n.vx / sp) * Math.min(sp, temp * 8);
        n.y += (n.vy / sp) * Math.min(sp, temp * 8);
        n.x = Math.max(40, Math.min(w - 40, n.x));
        n.y = Math.max(40, Math.min(h - 40, n.y));
      }
    }
  };

  GraphView.prototype.render = function () {
    var self = this;
    this.edgeLayer.innerHTML = ""; this.nodeLayer.innerHTML = "";
    var pathSet = {};
    for (var p = 0; p < this.highlightPath.length - 1; p++) {
      pathSet[this.highlightPath[p] + ">" + this.highlightPath[p + 1]] = true;
      pathSet[this.highlightPath[p + 1] + ">" + this.highlightPath[p]] = true;
    }
    this.edges.forEach(function (e) {
      var a = self.nodes[e.source], b = self.nodes[e.target];
      if (!a || !b) return;
      var hl = pathSet[e.source + ">" + e.target];
      var line = document.createElementNS(SVGNS, "line");
      line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
      line.setAttribute("x2", b.x); line.setAttribute("y2", b.y);
      line.setAttribute("class", "graph-edge" + (hl ? " hl" : "") +
        (e.review === "APPROVED" ? " approved" : ""));
      line.setAttribute("stroke-width", hl ? 3 : 1.2);
      self.edgeLayer.appendChild(line);
      var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      var lbl = document.createElementNS(SVGNS, "text");
      lbl.setAttribute("x", mx); lbl.setAttribute("y", my - 2);
      lbl.setAttribute("class", "graph-edge-label");
      lbl.textContent = e.label;
      self.edgeLayer.appendChild(lbl);
    });
    Object.keys(this.nodes).forEach(function (id) {
      var n = self.nodes[id];
      var g = document.createElementNS(SVGNS, "g");
      g.setAttribute("class", "graph-node" + (n.focus ? " focus" : "") +
        (self.selected === id ? " selected" : "") +
        (self.highlightPath.indexOf(id) > -1 ? " on-path" : ""));
      g.setAttribute("transform", "translate(" + n.x + "," + n.y + ")");
      var r = 10 + Math.min(14, (n.evidence || 0));
      var c = document.createElementNS(SVGNS, "circle");
      c.setAttribute("r", r);
      c.setAttribute("fill", TYPE_COLORS[n.type] || "#94a3b8");
      g.appendChild(c);
      var t = document.createElementNS(SVGNS, "text");
      t.setAttribute("class", "graph-node-label");
      t.setAttribute("y", r + 12);
      t.textContent = n.label;
      g.appendChild(t);
      self._bindNode(g, n);
      self.nodeLayer.appendChild(g);
    });
  };

  GraphView.prototype._bindNode = function (g, n) {
    var self = this, dragging = false, moved = false;
    g.addEventListener("mousedown", function (e) {
      e.stopPropagation(); dragging = true; moved = false;
    });
    window.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      moved = true; n.fixed = true;
      n.x += e.movementX / self.scale; n.y += e.movementY / self.scale;
      self.render();
    });
    window.addEventListener("mouseup", function () { dragging = false; });
    g.addEventListener("click", function (e) {
      e.stopPropagation();
      if (moved) return;
      self.selected = n.id;
      self.render();
      if (self.opts.onSelect) self.opts.onSelect(n);
    });
    g.addEventListener("dblclick", function (e) {
      e.stopPropagation();
      if (self.opts.onExpand) self.opts.onExpand(n);
    });
  };

  GraphView.prototype.focusNode = function (id) {
    var n = this.nodes[id];
    if (!n) return;
    var w = this.container.clientWidth, h = this.container.clientHeight;
    this.scale = 1.2;
    this.tx = w / 2 - n.x * this.scale; this.ty = h / 2 - n.y * this.scale;
    this.selected = id; this._applyTransform(); this.render();
  };

  GraphView.prototype.setPath = function (ids) { this.highlightPath = ids || []; this.render(); };
  GraphView.prototype.reset = function () {
    this.scale = 1; this.tx = 0; this.ty = 0; this.highlightPath = [];
    this.selected = null; this._applyTransform(); this.render();
  };

  window.GraphView = GraphView;
  window.GRAPH_TYPE_COLORS = TYPE_COLORS;
})();
