// QA bridge for Wood Block Journey (Phaser 3.55).
// Installed as a Playwright init script in every frame. It does not change game behaviour;
// it captures the Phaser.Game instance and exposes a small read/arrange API on window.__WBJ_QA__.
// In-house, this shim is replaced by a dev-owned Game Test Bridge contract (same method names).
(() => {
  if (window.__WBJ_QA_INSTALLED__) return;
  window.__WBJ_QA_INSTALLED__ = true;

  // 1) Capture the game instance when Phaser registers itself on window.
  let _P;
  try {
    Object.defineProperty(window, 'Phaser', {
      configurable: true,
      get() { return _P; },
      set(v) {
        _P = v;
        try {
          const boot = v.Game.prototype.boot;
          v.Game.prototype.boot = function () { window.__PHASER_GAME__ = this; return boot.apply(this, arguments); };
        } catch (e) { window.__WBJ_QA_HOOK_ERR__ = String(e); }
      },
    });
  } catch (e) { window.__WBJ_QA_HOOK_ERR__ = String(e); }

  // 2) Collect uncaught errors for the "no JS errors" oracle.
  window.__WBJ_QA_ERRORS__ = [];
  window.addEventListener('error', (e) => window.__WBJ_QA_ERRORS__.push(String(e.message || e)));
  window.addEventListener('unhandledrejection', (e) => window.__WBJ_QA_ERRORS__.push('unhandledrejection: ' + String(e.reason)));

  const G = () => window.__PHASER_GAME__;
  const S = () => G() && G().scene.getScene('GAME_SCENE');

  const worldToCss = (wx, wy) => {
    const g = G(), cam = S().cameras.main, r = g.canvas.getBoundingClientRect();
    const k = r.width / g.scale.width;
    const gx = (wx - cam.midPoint.x) * cam.zoom + cam.width / 2 + cam.x;
    const gy = (wy - cam.midPoint.y) * cam.zoom + cam.height / 2 + cam.y;
    return { x: r.x + gx * k, y: r.y + gy * k };
  };
  const boardMatrix = () => S().main.board.dataBoard.map(row => row.map(c => c.value));
  const pieceCells = (data) => {
    const cells = [];
    (data || []).forEach((row, y) => row.forEach((c, x) => { if (c && c.texture) cells.push([y, x]); }));
    return cells;
  };

  window.__WBJ_QA__ = {
    version: '1.0',
    ready() {
      const s = S();
      return !!(s && s.sys.settings.active && s.main && s.main.board && s.footer && s.footer.pieces);
    },
    currentScene() {
      const g = G(); if (!g) return null;
      const keys = g.scene.getScenes(true).map(s => s.sys.settings.key).filter(k => k !== 'GLOBAL_SCENE');
      return keys[0] || null;
    },
    nodeCss(name) {
      // Poco-style lookup: first visible display object with this name in any active scene
      const g = G();
      const find = (o, vis) => {
        const v = vis && o.visible !== false;
        if (o.name === name && v) return o;
        if (o.list) for (const c of o.list) { const r = find(c, v); if (r) return r; }
        return null;
      };
      for (const sc of g.scene.getScenes(true)) {
        for (const o of sc.children.list) {
          const hit = find(o, true);
          if (hit) {
            const b = hit.getBounds(), cam = sc.cameras.main, r = g.canvas.getBoundingClientRect(), k = r.width / g.scale.width;
            const gx = (b.centerX - cam.midPoint.x) * cam.zoom + cam.width / 2 + cam.x;
            const gy = (b.centerY - cam.midPoint.y) * cam.zoom + cam.height / 2 + cam.y;
            return { x: r.x + gx * k, y: r.y + gy * k, scene: sc.sys.settings.key };
          }
        }
      }
      return null;
    },
    phaserVersion() { return window.Phaser && window.Phaser.VERSION; },
    activeScenes() { return G().scene.getScenes(true).map(s => s.sys.settings.key); },
    errors() { return window.__WBJ_QA_ERRORS__.slice(); },
    fps() { return Math.round(G().loop.actualFps * 10) / 10; },
    canvasSize() { const r = G().canvas.getBoundingClientRect(); return { w: r.width, h: r.height, gw: G().scale.width, gh: G().scale.height }; },
    renderer() { return G().renderer.type === 2 ? 'WEBGL' : 'CANVAS'; },

    // ---- state oracles -------------------------------------------------
    tutorialState() { return S().tutorialManager.state; },
    inputEnabled() { return S().input.enabled; },
    isGameOver() { return !!S().isGameOver; },
    animating() { return S().checkAnimPlaying(); },
    score() { return S().getCurrentScoreByMode(); },
    bestScore() { return S().getBestScore() || 0; },
    targetScore() { return S().levelManager.getCurrentTargetScore(); },
    levelTargets() { return S().levelManager.levels.slice(); },
    levelIndex() { return S().levelManager.getCurrentIndex(); },
    fen() { return S().getFen(); },
    state() {
      const board = boardMatrix();
      return { fen: S().getFen(), score: S().getCurrentScoreByMode(), board, filled: board.flat().reduce((a, b) => a + b, 0),
               pieces: this.pieces(), screens: this.openScreens(), input: S().input.enabled, gameOver: !!S().isGameOver,
               tutorial: S().tutorialManager.state };
    },
    board() { return boardMatrix(); },
    filled() { return boardMatrix().flat().reduce((a, b) => a + b, 0); },
    openScreens() {
      const out = [];
      for (const sc of G().scene.getScenes(true)) {
        for (const o of sc.children.list) if (o.name && /_SCREEN$/.test(o.name) && o.visible) out.push(o.name);
      }
      return out;
    },
    screenTexts(name) {
      // all visible text nodes inside a named screen container (Poco-style UI tree read)
      const out = [];
      const walk = (o, vis) => {
        const v = vis && o.visible !== false;
        if (typeof o.text === 'string' && v && o.text !== '') out.push(o.text);
        if (o.list) o.list.forEach(c => walk(c, v));
      };
      for (const sc of G().scene.getScenes(true)) for (const o of sc.children.list) if (o.name === name) walk(o, true);
      return out;
    },
    uiTree(name, depth = 4) {
      const node = (o, d) => ({ type: o.type, name: o.name || undefined, frame: o.frame && o.frame.name !== '__BASE' ? o.frame.name : undefined,
        text: typeof o.text === 'string' && o.text ? o.text : undefined, visible: o.visible,
        children: o.list && d < depth ? o.list.map(c => node(c, d + 1)) : undefined });
      for (const sc of G().scene.getScenes(true)) for (const o of sc.children.list) if (o.name === name) return node(o, 0);
      return null;
    },
    headerScoreText() { const b = S().header.mainScoreBlock; const t = []; const w = o => { if (typeof o.text === 'string') t.push(o.text); if (o.list) o.list.forEach(w); }; w(b); return t; },
    pieces() {
      const p = S().footer.pieces;
      return p.piecesActive.map((a, slot) => {
        const obj = p.allPieces[a.position];
        return { slot, used: !!a.used, type: a.type, direction: a.direction, cells: pieceCells(obj.data),
                 canMove: obj.isCanMove !== false, visible: !!obj.visible };
      });
    },
    matchStore() {
      const st = S().storage.getState();
      const m = st.match && st.match.match && st.match.match.single;
      return m ? { score: m.score, level: m.level, status: m.status, rescued: m.rescued, fen: m.data && m.data.fen } : null;
    },
    highlight() {
      const b = S().main.board, out = [];
      b.dataBoard.forEach((row, y) => row.forEach((c, x) => { try { if (c.cell && c.cell.isHighlight && c.cell.isHighlight()) out.push([y, x]); } catch (e) {} }));
      return out;
    },
    suggest() { return (S().main.board.suggestCells || []).map(c => [c.y, c.x]); },
    dropPos() { const b = S().main.board; return b.pX === null || b.pX === undefined ? null : [b.pY, b.pX]; },

    // ---- geometry (CSS px inside the game frame) ---------------------------
    cellCss(row, col) {
      const c = S().main.board.dataBoard[row][col];
      const m = S().main.board.getWorldTransformMatrix();
      return worldToCss(m.tx + c.cell.x, m.ty + c.cell.y);  // cell image origin is its centre
    },
    cellSizeCss() { const a = this.cellCss(0, 0), b = this.cellCss(0, 1); return b.x - a.x; },
    pieceCss(slot) {
      const p = S().footer.pieces, obj = p.allPieces[p.piecesActive[slot].position];
      const b = obj.getBounds();
      return worldToCss(b.centerX, b.centerY);
    },
    pieceCellsWorld(slot) {
      const p = S().footer.pieces, obj = p.allPieces[p.piecesActive[slot].position];
      const walk = (o, acc) => { if (o.list) o.list.forEach(c => walk(c, acc)); else if (o.type === 'Image' && o.visible) { const m = o.getWorldTransformMatrix(); acc.push([Math.round(m.tx), Math.round(m.ty), o.frame && o.frame.name]); } return acc; };
      return { self: walk(obj, []), wrap: obj.wrapPiece ? walk(obj.wrapPiece, []) : [] };
    },
    dragAnchorWorld(slot) {
      // world position of the dragged piece's first occupied cell (row-major), or null if not visible
      const cells = this.pieceCellsWorld(slot).self.filter(c => c[2] && c[2] !== 'gem/gem_transparent');
      if (!cells.length) return null;
      cells.sort((a, b) => (a[1] - b[1]) || (a[0] - b[0]));
      const top = cells[0][1];
      const row = cells.filter(c => Math.abs(c[1] - top) < 6).sort((a, b) => a[0] - b[0]);
      return [row[0][0], row[0][1]];
    },
    cssPerWorld() { const g = G(), cam = S().cameras.main, r = g.canvas.getBoundingClientRect(); return cam.zoom * r.width / g.scale.width; },
    boardCellWorld(row, col) { const c = S().main.board.dataBoard[row][col]; const m = c.cell.getWorldTransformMatrix(); return [Math.round(m.tx), Math.round(m.ty)]; },
    pieceDebug(slot) {
      const p = S().footer.pieces, obj = p.allPieces[p.piecesActive[slot].position];
      const b = obj.getBounds(), w = obj.wrapPiece ? obj.wrapPiece.getBounds() : null;
      return { obj: [obj.x, obj.y, b.x, b.y, b.width, b.height], wrap: w && [w.x, w.y, w.width, w.height], vis: obj.visible, cells: obj.list.length };
    },

    // ---- arrange (test-only state injection; the in-house Game Test Bridge would own this) ----
    skipTutorial() { const t = S().tutorialManager; if (t.isRunning()) t.handleCompleteTutorial(); return t.state; },
    setBoard(boardFen) {
      const b = S().main.board;
      const data = b.getBoardByFen(boardFen + ' l');
      b.clearBoard(); b.startGame(data);
      return b.getFenByBoard();
    },
    setPieces(specs) {
      // Mirrors the dealer's invariant: every slot uses a DIFFERENT piece object (randomPieces never
      // deals the same allPieces index twice). The game's own showAvailablePieces() does not, so two
      // identical pieces would share one sprite — a test-hook artefact we must not create.
      const p = S().footer.pieces, taken = new Set(), active = [];
      p.allPieces.forEach(o => { try { o.reset(); } catch (e) {} });
      for (const s of specs) {
        const dir = s.direction ?? null, rev = !!s.isReverse;
        const idx = p.allPieces.findIndex((o, i) => !taken.has(i) && o.type === s.type && (o.direction ?? null) === dir && !!o.isReverse === rev);
        if (idx < 0) throw new Error('no free piece object for ' + JSON.stringify(s));
        taken.add(idx);
        active.push({ position: idx, texture: 'gameplay-32-resources', frame: 'gem/gem', type: s.type, direction: dir, isReverse: rev });
      }
      p.piecesActive = active; p.setActivePieces(); p.drawPieces();
      return p.getFenByPieces();
    },
    pieceCatalog() {
      const seen = {}, p = S().footer.pieces;
      p.allPieces.forEach(o => { const k = o.type + '|' + (o.direction || '') + '|' + o.isReverse; if (!seen[k]) seen[k] = { type: o.type, direction: o.direction, isReverse: o.isReverse, cells: pieceCells(o.data) }; });
      return Object.values(seen);
    },
  };
})();
