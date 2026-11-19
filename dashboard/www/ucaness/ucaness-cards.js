/*
 * UCANESS HOME ASSISTANT : cartes Lovelace dans le style du portail UCANESS.
 * Un seul fichier, sans dépendance ni compilation. Licence MIT (voir LICENSE du dépôt).
 *
 * Cartes fournies :
 *   custom:ucaness-layout-card  en-tête + colonnes (300 px | reste | 300 px), une seule colonne sur téléphone
 *   custom:ucaness-header-card  bandeau titre, onglets, heure, liaison, alertes
 *   custom:ucaness-panel-card   panneau titré (losange, barres orange et cyan), carrousel ou onglets facultatifs
 *   custom:ucaness-flow-card    vue en direct de la maison : image, boules, onduleur, flux animés
 *   custom:ucaness-soc-card     anneau de charge de la batterie
 *   custom:ucaness-note-card    texte replié sur quelques lignes, terminé par « … », déplié d'un appui
 *
 * Conventions de signe de l'intégration ucaness : batterie > 0 = charge, réseau > 0 = soutirage.
 */

const UC_VERSION = '0.2.3';

/* Dossier où se trouve ce fichier (en général /local/ucaness/). */
const UC_BASE = (() => {
  try { return new URL('.', import.meta.url).href; } catch (e) { return '/local/ucaness/'; }
})();

/* ------------------------------------------------------------------ outils */

const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const UC_FONT = "'Times New Roman', Tinos, 'Liberation Serif', serif";

/* Mode allégé, pour les tablettes peu puissantes : animations coupées.
 * « ?leger=1 » dans l'adresse l'active sur cet appareil (mémorisé), « ?leger=0 » le retire. */
const UC_LIGHT = (() => {
  try {
    const q = new URLSearchParams(window.location.search).get('leger');
    if (q === '1') window.localStorage.setItem('ucaness-leger', '1');
    if (q === '0') window.localStorage.removeItem('ucaness-leger');
    return window.localStorage.getItem('ucaness-leger') === '1';
  } catch (e) { return false; }
})();

/** Vrai si l'état d'une des entités a changé depuis le dernier appel pour cette carte.
 *  Home Assistant transmet `hass` à chaque changement d'état de la maison : on ne redessine
 *  la carte que pour ses propres entités. */
function ucChanged(card, hass, ids) {
  const next = ids.map((id) => (hass && hass.states ? hass.states[id] : undefined));
  const prev = card._ucSeen;
  card._ucSeen = next;
  if (!prev || prev.length !== next.length) return true;
  return next.some((st, i) => st !== prev[i]);
}

function ucNumber(hass, value, digits) {
  const lang = (hass && hass.locale && hass.locale.language) || (hass && hass.language) || 'fr';
  try {
    return new Intl.NumberFormat(lang, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
  } catch (e) {
    return Number(value).toFixed(digits);
  }
}

/** État numérique d'une entité, ou null si absente ou indisponible. */
function ucNum(hass, entityId) {
  const st = entityId && hass && hass.states ? hass.states[entityId] : undefined;
  if (!st) return null;
  const v = parseFloat(st.state);
  return Number.isFinite(v) ? v : null;
}

/** Puissance en W (convertit kW si l'unité l'indique). */
function ucWatts(hass, entityId) {
  const v = ucNum(hass, entityId);
  if (v === null) return null;
  const unit = (hass.states[entityId].attributes || {}).unit_of_measurement;
  return unit === 'kW' ? v * 1000 : v;
}

/** Valeur affichée d'une entité avec son unité (« 51,8 V »). */
function ucDisplay(hass, entityId) {
  const st = entityId && hass && hass.states ? hass.states[entityId] : undefined;
  if (!st || st.state === 'unavailable' || st.state === 'unknown') return '—';
  const unit = (st.attributes || {}).unit_of_measurement || '';
  const v = parseFloat(st.state);
  if (!Number.isFinite(v)) return st.state;
  let digits = Math.abs(v) >= 10 ? 1 : 2;
  if (unit === 'Hz') digits = 2;
  if (unit === '%' || unit === 'W') digits = 0;
  return `${ucNumber(hass, v, digits)}${unit ? ' ' + unit : ''}`;
}

function ucMoreInfo(node, entityId) {
  if (!entityId) return;
  node.dispatchEvent(new CustomEvent('hass-more-info', { bubbles: true, composed: true, detail: { entityId } }));
}

function ucNavigate(path) {
  window.history.pushState(null, '', path);
  window.dispatchEvent(new CustomEvent('location-changed', { detail: { replace: false } }));
}

/** Crée les cartes enfants avec les outils de Home Assistant. */
async function ucCreateCards(configs, hass, host) {
  const helpers = window.loadCardHelpers ? await window.loadCardHelpers() : null;
  return (configs || []).map((conf) => {
    const make = () => {
      const el = helpers ? helpers.createCardElement(conf) : document.createElement('div');
      el.hass = host._hass || hass;
      return el;
    };
    let el = make();
    el.addEventListener('ll-rebuild', (ev) => {
      ev.stopPropagation();
      const fresh = make();
      fresh.hass = host._hass;
      el.replaceWith(fresh);
      el = fresh;
    });
    return el;
  });
}

/* Polices locales (Tinos, métriquement identique à Times New Roman), chargées une seule fois. */
(function ucInjectFonts() {
  if (typeof document === 'undefined' || document.getElementById('ucaness-fonts')) return;
  const base = UC_BASE;
  const style = document.createElement('style');
  style.id = 'ucaness-fonts';
  style.textContent = [400, 700].map((w) => `@font-face{font-family:Tinos;font-style:normal;font-weight:${w};font-display:swap;src:url(${base}fonts/tinos-latin-${w}-normal.woff2) format('woff2')}`).join('');
  document.head.appendChild(style);
})();

/* Styles communs (variables surchargeables par le thème). */
const UC_BASE_CSS = `
  :host {
    --uc-font: var(--ucaness-font, ${UC_FONT});
    --uc-text: var(--ucaness-text, #FFFFFF);
    --uc-muted: var(--ucaness-muted, #7DABCD);
    --uc-label: var(--ucaness-label, #02E8EA);
    --uc-value: var(--ucaness-value, #00FFFF);
    --uc-accent: var(--ucaness-accent, #2AB7E2);
    --uc-tab: var(--ucaness-tab, #00D1D6);
    --uc-tab-border: var(--ucaness-tab-border, #446E74);
    --uc-orange: var(--ucaness-orange, #F39C12);
    --uc-green: var(--ucaness-green, #2ECC71);
    --uc-panel-bg: var(--ucaness-panel-bg, linear-gradient(180deg, rgba(10,27,54,0.92) 0%, rgba(8,20,42,0.92) 100%));
    --uc-panel-border: var(--ucaness-panel-border, #12345E);
    --uc-title-bg: var(--ucaness-title-bg, linear-gradient(180deg, #154B84 0%, #0B2C55 100%));
    font-family: var(--uc-font);
    color: var(--uc-text);
  }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
  ${UC_LIGHT ? '* { animation: none !important; transition: none !important; }' : ''}
`;

const UC_DIAMOND = `<span class="diamond" aria-hidden="true"><span><i></i></span></span>`;
const UC_BARS = `<span class="bars" aria-hidden="true"><i class="o"></i><i></i><i></i></span>`;
const UC_TITLE_CSS = `
  .titlebar { position: relative; height: 40px; display: flex; align-items: center; }
  .titlebar .tab { height: 36px; display: flex; align-items: center; gap: 10px; padding: 0 30px 0 6px; background: var(--uc-title-bg); clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 100%, 0 100%); }
  .titlebar h2 { margin: 0; font: 400 19px var(--uc-font); color: var(--uc-text); white-space: nowrap; }
  .titlebar .line { position: absolute; left: 0; right: 0; bottom: 1px; height: 2px; background: linear-gradient(90deg, var(--uc-accent) 0%, rgba(42,183,226,0.35) 60%, rgba(42,183,226,0) 100%); }
  .titlebar .status { margin-left: auto; padding-right: 6px; font-size: 13px; color: var(--uc-muted); }
  .diamond { width: 26px; height: 26px; box-sizing: border-box; border: 1px solid #3A86C8; background: #0A2546; display: flex; align-items: center; justify-content: center; flex: 0 0 26px; }
  .diamond > span { width: 11px; height: 11px; box-sizing: border-box; border: 1.5px solid #6FD6F5; transform: rotate(45deg); display: flex; align-items: center; justify-content: center; }
  .diamond i { width: 3px; height: 3px; background: #BFF2FF; }
  .bars { display: flex; gap: 3px; margin: 0 0 16px 2px; }
  .bars i { width: 8px; height: 6px; background: var(--uc-accent); transform: skewX(-40deg); }
  .bars i.o { background: var(--uc-orange); }
`;

/* ------------------------------------------------------------------ en-tête */

class UcanessHeaderCard extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({ title: 'UCANESS HOME ASSISTANT', site: 'Maison', tabs: [], alert_entities: [] }, config || {});
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const c = this._config || {};
    const ids = [c.connectivity_entity, c.subtitle_entity, ...(c.alert_entities || []), ...(c.tabs || []).map((t) => t.entity)].filter(Boolean);
    if (ucChanged(this, hass, ids)) this._render();
  }

  connectedCallback() {
    this._timer = setInterval(() => this._render(), 30000);
    this._onLoc = () => this._render();
    window.addEventListener('location-changed', this._onLoc);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    window.removeEventListener('location-changed', this._onLoc);
  }

  getCardSize() { return 1; }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const hass = this._hass;
    const lang = (hass && hass.locale && hass.locale.language) || 'fr';
    const now = new Date();
    const time = now.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' });
    const date = now.toLocaleDateString(lang, { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' });
    const path = window.location.pathname;
    const alerts = (c.alert_entities || []).filter((e) => hass && hass.states[e] && hass.states[e].state === 'on').length;
    const conn = c.connectivity_entity && hass ? hass.states[c.connectivity_entity] : null;
    const online = conn ? conn.state === 'on' : null;
    const subtitle = c.subtitle_entity && hass && hass.states[c.subtitle_entity] ? hass.states[c.subtitle_entity].state : (c.subtitle || '');
    const tabs = (c.tabs || []).map((t, i) => {
      const active = path.endsWith('/' + String(t.path).replace(/^\/+/, '').split('/').pop());
      const extra = t.entity && hass && hass.states[t.entity] ? ` <b>${esc(ucDisplay(hass, t.entity))}</b>` : '';
      return `<button type="button" class="tab${active ? ' on' : ''}" data-i="${i}" ${active ? 'aria-current="page"' : ''}><span>${esc(t.title)}${extra}</span></button>`;
    }).join('');
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        header { position: relative; height: 62px; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; background: linear-gradient(180deg, #0B2F5C 0%, #061B3D 100%); border-bottom: 1px solid #1C5C9E; box-shadow: 0 2px 14px rgba(0,0,0,0.55); overflow: hidden; }
        .plate { position: absolute; left: 50%; top: 0; width: min(620px, 52%); height: 58px; transform: translateX(-50%); clip-path: polygon(0 0, 100% 0, 95% 100%, 5% 100%); background: linear-gradient(180deg, #1A6FBE 0%, #0E4382 62%, #0A2F5E 100%); overflow: hidden; }
        .sweep { position: absolute; top: 0; left: 0; width: 140px; height: 58px; background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(160,220,255,0.22) 50%, rgba(255,255,255,0) 100%); animation: sweep 7s ease-in-out infinite; }
        @keyframes sweep { 0% { transform: translateX(-120%); } 60%, 100% { transform: translateX(520%); } }
        h1 { position: relative; margin: 0; height: 58px; display: flex; align-items: center; justify-content: center; font: 700 clamp(18px, 2.4vw, 31px) var(--uc-font); background: linear-gradient(180deg, #FFFFFF 78%, #7DABCD 100%); -webkit-background-clip: text; background-clip: text; color: transparent; white-space: nowrap; }
        .left, .right { display: flex; align-items: center; gap: 14px; z-index: 1; }
        .site { display: flex; align-items: center; gap: 8px; font: 500 19px var(--uc-font); color: #C9CACA; }
        .tab { height: 44px; padding: 0 2px; border: 0; background: transparent; cursor: pointer; font: inherit; }
        .tab span { display: block; padding: 5px 12px; border: 1px solid var(--uc-tab-border); color: var(--uc-text); font: 400 16px var(--uc-font); }
        .tab.on span { background: var(--uc-tab); }
        .tab b { font-weight: 400; color: var(--uc-green); }
        .tab.on b { color: var(--uc-text); }
        .bell { position: relative; display: flex; }
        .badge { position: absolute; right: -9px; top: -7px; min-width: 18px; height: 16px; padding: 0 4px; box-sizing: border-box; border-radius: 8px; background: #E5484D; font: 700 11px var(--uc-font); display: flex; align-items: center; justify-content: center; }
        .clock { display: flex; flex-direction: column; align-items: flex-end; line-height: 1.1; }
        .clock b { font: 700 22px var(--uc-font); }
        .clock span { font-size: 12px; color: var(--uc-muted); }
        @media (max-width: 900px) {
          header { height: auto; min-height: 56px; flex-wrap: wrap; gap: 6px 12px; padding: 6px 10px; }
          .plate { display: none; }
          .site span { display: none; }
          .left, .right { gap: 8px; }
          .clock b { font-size: 18px; }
        }
      </style>
      <header>
        <div class="plate"><div class="sweep" aria-hidden="true"></div><h1>${esc(c.title)}</h1></div>
        <div class="left">
          <span class="site"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#F0883E" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M3 11.5L12 4l9 7.5"/><path d="M6 10v10h12V10"/></svg><span>${esc(c.site)}</span></span>
          <nav aria-label="Vues">${tabs}</nav>
        </div>
        <div class="right">
          ${(c.alert_entities || []).length ? `<span class="bell" role="img" aria-label="${alerts} alerte(s) en cours"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#7DABCD" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20a2 2 0 0 0 4 0"/></svg>${alerts ? `<span class="badge">${alerts}</span>` : ''}</span>` : ''}
          ${online === null ? '' : `<svg role="img" aria-label="${online ? 'Liaison au cloud en ligne' : 'Liaison au cloud perdue'}" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="${online ? '#2ED198' : '#E5484D'}" stroke-width="2" stroke-linecap="round"><path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19.5" r="1" fill="currentColor"/></svg>`}
          <span class="clock"><b>${esc(time)}</b><span>${esc(date)}${subtitle ? ' · ' + esc(subtitle) : ''}</span></span>
        </div>
      </header>`;
    this.shadowRoot.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => {
      const t = c.tabs[Number(b.dataset.i)];
      if (t && t.path) ucNavigate(t.path);
    }));
  }
}

/* ------------------------------------------------------------------ mise en page */

class UcanessLayoutCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.columns) || !config.columns.length) {
      throw new Error('ucaness-layout-card : « columns » est obligatoire (liste de colonnes avec « cards »).');
    }
    this._config = config;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    (this._children || []).forEach((el) => { el.hass = hass; });
    if (this._header) this._header.hass = hass;
  }

  getCardSize() { return 12; }

  async _build() {
    const c = this._config;
    const widths = c.columns.map((col) => col.width || '1fr').join(' ');
    const main = Number.isInteger(c.mobile_first_column) ? c.mobile_first_column : Math.floor(c.columns.length / 2);
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; min-height: 100%; background: var(--ucaness-page-bg, radial-gradient(ellipse at 50% 42%, #0D2A58 0%, #071A3A 48%, #030B20 100%)); }
        .wrap { display: flex; flex-direction: column; gap: 10px; padding-bottom: 14px; }
        .grid { display: grid; grid-template-columns: ${widths}; gap: ${c.gap || '12px'}; padding: 0 16px; align-items: start; }
        .col { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
        @media (max-width: ${c.mobile_breakpoint || 900}px) {
          .grid { grid-template-columns: 1fr; padding: 0 8px; }
          .col[data-i="${main}"] { order: -1; }
        }
      </style>
      <div class="wrap"><div class="head"></div><div class="grid"></div></div>`;
    const grid = this.shadowRoot.querySelector('.grid');
    if (c.header) {
      this._header = document.createElement('ucaness-header-card');
      this._header.setConfig(c.header);
      if (this._hass) this._header.hass = this._hass;
      this.shadowRoot.querySelector('.head').appendChild(this._header);
    }
    this._children = [];
    for (let i = 0; i < c.columns.length; i++) {
      const colEl = document.createElement('div');
      colEl.className = 'col';
      colEl.dataset.i = String(i);
      grid.appendChild(colEl);
      const cards = await ucCreateCards(c.columns[i].cards, this._hass, this);
      cards.forEach((el) => { colEl.appendChild(el); this._children.push(el); });
    }
  }
}

/* ------------------------------------------------------------------ panneau */

class UcanessPanelCard extends HTMLElement {
  setConfig(config) {
    if (!config || (!config.cards && !config.slides)) {
      throw new Error('ucaness-panel-card : indiquez « cards » ou « slides ».');
    }
    this._config = config;
    this._slide = 0;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    (this._children || []).flat().forEach((el) => { el.hass = hass; });
    this._status();
  }

  connectedCallback() { this._startTimer(); }

  /** Défilement automatique du carrousel ; relancé après un choix manuel pour laisser le temps de lire. */
  _startTimer() {
    clearInterval(this._timer);
    const c = this._config || {};
    if (this.isConnected && c.slides && c.slides.length > 1 && c.interval !== 0 && !c.tabs) {
      this._timer = setInterval(() => this._show((this._slide + 1) % c.slides.length), (c.interval || 8) * 1000);
    }
  }

  disconnectedCallback() { clearInterval(this._timer); }

  getCardSize() { return 4; }

  async _build() {
    const c = this._config;
    const slides = c.slides || [{ title: c.title, cards: c.cards }];
    // tabs: true → titre fixe, onglets nommés en haut du panneau, pas de défilement automatique.
    const tabs = !!(c.tabs && c.slides && c.slides.length > 1);
    const title = tabs ? (c.title || '') : (slides[0].title || '');
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}${UC_TITLE_CSS}
        :host { display: block; }
        .body { position: relative; box-sizing: border-box; padding: 8px; display: flex; flex-direction: column; gap: 8px; background: var(--uc-panel-bg); border: 1px solid var(--uc-panel-border); border-top: 0; border-bottom: 2px solid rgba(125,171,205,0.45); }
        .body.dots-on { padding-bottom: 24px; }
        .slide { display: flex; flex-direction: column; gap: 8px; animation: ucIn .45s ease-out both; }
        .slide[hidden] { display: none; }
        @keyframes ucIn { from { opacity: 0; transform: translateY(-12px); } to { opacity: 1; transform: none; } }
        .dots { position: absolute; left: 0; right: 0; bottom: 0; display: flex; justify-content: center; }
        .dots button { width: 44px; height: 22px; border: 0; background: transparent; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .dots i { display: block; width: 14px; height: 3px; background: #4E6C93; }
        .dots button.on i { width: 24px; background: #FFFFFF; }
        .tabs { display: flex; gap: 6px; }
        .tabs button { flex: 1 1 0; min-width: 0; min-height: 48px; box-sizing: border-box; padding: 4px 2px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; border: 1px solid #1E4E85; border-radius: 6px; background: rgba(10,30,60,0.6); color: var(--uc-text); font: 400 12px var(--uc-font); cursor: pointer; --mdc-icon-size: 18px; }
        .tabs button ha-icon { color: #9CC9F5; }
        .tabs button[aria-selected="true"] { border-color: #22E0F0; background: rgba(18,80,150,0.55); box-shadow: 0 0 10px rgba(34,224,240,0.55); }
      </style>
      <section aria-label="${esc(title)}">
        <div class="titlebar"><div class="tab">${UC_DIAMOND}<h2>${esc(title)}</h2></div>${c.slides && !tabs ? '' : UC_BARS}<span class="status"></span><div class="line" aria-hidden="true"></div></div>
        <div class="body${slides.length > 1 && !tabs ? ' dots-on' : ''}"></div>
      </section>`;
    const body = this.shadowRoot.querySelector('.body');
    this._children = [];
    if (tabs) {
      const bar = document.createElement('div');
      bar.className = 'tabs';
      bar.setAttribute('role', 'tablist');
      bar.setAttribute('aria-label', title);
      bar.innerHTML = slides.map((s, i) => `<button type="button" role="tab" aria-selected="${i ? 'false' : 'true'}" data-i="${i}">${s.icon ? `<ha-icon icon="${esc(s.icon)}"></ha-icon>` : ''}<span>${esc(s.tab || s.title || i + 1)}</span></button>`).join('');
      bar.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => this._show(Number(b.dataset.i))));
      body.appendChild(bar);
    }
    for (let i = 0; i < slides.length; i++) {
      const s = document.createElement('div');
      s.className = 'slide';
      if (i) s.hidden = true;
      body.appendChild(s);
      const cards = await ucCreateCards(slides[i].cards || (slides[i].card ? [slides[i].card] : []), this._hass, this);
      cards.forEach((el) => s.appendChild(el));
      this._children.push(cards);
    }
    if (slides.length > 1 && !tabs) {
      const dots = document.createElement('div');
      dots.className = 'dots';
      dots.innerHTML = slides.map((s, i) => `<button type="button" aria-label="Afficher ${esc(s.title || i + 1)}" class="${i ? '' : 'on'}" data-i="${i}"><i></i></button>`).join('');
      dots.querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { this._show(Number(b.dataset.i)); this._startTimer(); }));
      body.appendChild(dots);
    }
    this._status();
  }

  _show(i) {
    const slides = this._config.slides || [];
    if (!this.shadowRoot || !slides[i]) return;
    this._slide = i;
    this.shadowRoot.querySelectorAll('.slide').forEach((s, k) => { s.hidden = k !== i; });
    this.shadowRoot.querySelectorAll('.dots button').forEach((b, k) => b.classList.toggle('on', k === i));
    this.shadowRoot.querySelectorAll('.tabs button').forEach((b, k) => b.setAttribute('aria-selected', String(k === i)));
    if (this._config.tabs) return;  // onglets : le titre du panneau ne change pas
    this.shadowRoot.querySelector('.titlebar h2').textContent = slides[i].title || '';
    this.shadowRoot.querySelector('section').setAttribute('aria-label', slides[i].title || '');
  }

  _status() {
    const c = this._config;
    const el = this.shadowRoot && this.shadowRoot.querySelector('.status');
    if (!el || !c.status_entity || !this._hass) return;
    el.textContent = ucDisplay(this._hass, c.status_entity);
  }
}

/* ------------------------------------------------------------------ vue en direct */

const UC_FLOW_DEFAULTS = {
  image: UC_BASE + 'maison-exemple.svg',
  aspect_ratio: 1.45,
  image_area: { x: 0, y: 6.5, w: 100 },
  min_power: 30,
  calibration: false,
  nodes: {
    solar: { entity: 'sensor.uhome_puissance_solaire', label: 'Solaire', x: 44, y: 11.5, details: ['sensor.uhome_tension_solaire'], details_side: 'left' },
    grid: { entity: 'sensor.uhome_puissance_reseau', label: 'Réseau', x: 65, y: 11.5, details: ['sensor.uhome_tension_reseau', 'sensor.uhome_frequence_reseau'], details_side: 'right' },
    inverter: { label: 'Onduleur', x: 44, y: 46 },
    battery: { entity: 'sensor.uhome_puissance_batterie', soc_entity: 'sensor.uhome_soc', x: 20, y: 79, details: ['sensor.uhome_tension_batterie', 'sensor.uhome_courant_batterie'], details_side: 'right' },
    home: { entity: 'sensor.uhome_puissance_maison', label: 'Maison', x: 60, y: 79, details: [], details_side: 'right' },
  },
};

class UcanessFlowCard extends HTMLElement {
  static getStubConfig() { return {}; }

  setConfig(config) {
    const c = Object.assign({}, UC_FLOW_DEFAULTS, config || {});
    c.nodes = {};
    for (const k of Object.keys(UC_FLOW_DEFAULTS.nodes)) {
      c.nodes[k] = Object.assign({}, UC_FLOW_DEFAULTS.nodes[k], ((config || {}).nodes || {})[k] || {});
    }
    c.image_area = Object.assign({}, UC_FLOW_DEFAULTS.image_area, (config || {}).image_area || {});
    this._config = c;
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (ucChanged(this, hass, this._ids())) this._render();
  }

  /** Entités affichées par la carte (puissances, charge, détails). */
  _ids() {
    const ids = [];
    for (const n of Object.values(this._config.nodes)) {
      if (n.entity) ids.push(n.entity);
      if (n.soc_entity) ids.push(n.soc_entity);
      (n.details || []).forEach((d) => ids.push(d));
    }
    return ids;
  }

  /* L'âge du relevé (« il y a 20 s ») avance même sans nouvelle mesure. */
  connectedCallback() { this._timer = setInterval(() => this._render(), 30000); }

  disconnectedCallback() { clearInterval(this._timer); }

  getCardSize() { return 8; }

  /** Sens et intensité d'un flux : 'in' = vers l'onduleur, 'out' = depuis l'onduleur, null = au repos. */
  _flow(key) {
    const n = this._config.nodes[key];
    const w = ucWatts(this._hass, n.entity);
    if (w === null) return { w: null, dir: null };
    const v = n.invert ? -w : w;
    if (Math.abs(v) < this._config.min_power) return { w: v, dir: null };
    if (key === 'solar') return { w: v, dir: v > 0 ? 'in' : null };
    if (key === 'home') return { w: v, dir: v > 0 ? 'out' : null };
    if (key === 'battery') return { w: v, dir: v > 0 ? 'out' : 'in' };  // charge > 0 : de l'onduleur vers la batterie
    if (key === 'grid') return { w: v, dir: v > 0 ? 'in' : 'out' };     // soutirage > 0 : du réseau vers l'onduleur
    return { w: v, dir: null };
  }

  /** Tracé orthogonal de la boule vers l'onduleur (coordonnées en unités du SVG). */
  _route(key, W, H) {
    const c = this._config;
    const n = c.nodes[key];
    const inv = c.nodes.inverter;
    const P = (p) => [p[0] * W / 100, p[1] * H / 100];
    if (Array.isArray(n.path) && n.path.length >= 2) return n.path.map(P);
    const r = (key === 'solar' ? 6.75 : key === 'grid' ? 6.1 : 5.8) * W / 100;  // rayon des boules
    const iw = 7.7 * W / 100, ih = 4.5 * W / 100;                             // demi-onduleur
    const [nx, ny] = P([n.x, n.y]);
    const [ix, iy] = P([inv.x, inv.y]);
    if (ny < iy) {  // boule au-dessus de l'onduleur
      if (Math.abs(nx - ix) < iw * 0.6) return [[nx, ny + r], [nx, iy - ih]];
      const side = nx > ix ? ix + iw : ix - iw;
      return [[nx, ny + r], [nx, iy], [side, iy]];
    }
    // boule sous l'onduleur
    const sx = Math.max(ix - iw * 0.75, Math.min(ix + iw * 0.75, nx));
    if (Math.abs(nx - sx) < 1) return [[nx, ny - r], [sx, iy + ih]];
    const midY = iy + ih + Math.max(12, (ny - r - iy - ih) * 0.35);
    const endX = nx < ix ? ix - iw * 0.45 : ix + iw * 0.45;
    return [[nx, ny - r], [nx, midY], [endX, midY], [endX, iy + ih]];
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const hass = this._hass || { states: {} };
    const W = 1000, H = Math.round(1000 / c.aspect_ratio);
    const kw = (w) => (w === null ? '—' : ucNumber(hass, Math.abs(w) / 1000, 2));
    let paths = '';
    const flows = {};
    for (const key of ['solar', 'grid', 'battery', 'home']) {
      const f = this._flow(key);
      flows[key] = f;
      let pts = this._route(key, W, H);
      const active = f.dir !== null;
      if (active && f.dir === 'out') pts = pts.slice().reverse();
      const d = 'M' + pts.map((p) => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
      if (active) {
        const [ex, ey] = pts[pts.length - 1];
        const [px, py] = pts[pts.length - 2];
        const ang = Math.atan2(ey - py, ex - px);
        const a = 13, s = 0.6;
        const p1 = [ex - a * Math.cos(ang - s), ey - a * Math.sin(ang - s)];
        const p2 = [ex - a * Math.cos(ang + s), ey - a * Math.sin(ang + s)];
        paths += `<path class="flow" d="${d}"/><path class="pulse" d="${d}"/><path class="arrow" d="M${p1[0].toFixed(1)} ${p1[1].toFixed(1)} L${ex.toFixed(1)} ${ey.toFixed(1)} L${p2[0].toFixed(1)} ${p2[1].toFixed(1)}"/>`;
      } else {
        paths += `<path class="idle" d="${d}"/>`;
      }
    }
    const names = { solar: 'Solaire', grid: 'Réseau', battery: 'Batterie', home: 'Maison' };
    const nodeHtml = (key, cls, label) => {
      const n = c.nodes[key];
      const f = flows[key];
      const on = f.dir !== null;
      const det = (n.details || []).map((e) => esc(ucDisplay(hass, e))).join('<br>');
      const side = n.details_side === 'left' ? 'left' : 'right';
      return `
        <button type="button" class="ball ${cls}${on ? ' on' : ''}${f.w === null ? ' na' : ''}" style="left:${n.x}%;top:${n.y}%" data-entity="${esc(n.entity || '')}" aria-label="${esc((label || names[key]) + ' : ' + kw(f.w) + ' kW')}">
          ${label ? `<span class="lbl">${esc(label)}</span>` : ''}<span class="val">${key === 'battery' && f.w !== null && f.w < 0 ? '−' : ''}${esc(kw(f.w))}</span><span class="unit">kW</span>
        </button>
        ${det ? `<div class="det ${side} ${cls}" style="left:${n.x}%;top:${n.y}%">${det}</div>` : ''}`;
    };
    const inv = c.nodes.inverter;
    const bat = c.nodes.battery;
    const soc = ucNum(hass, bat.soc_entity);
    const bf = flows.battery;
    const batState = bf.dir === 'out' ? 'Chargement' : bf.dir === 'in' ? 'Décharge' : 'Veille';
    const home = c.nodes.home;
    let grid = '';
    if (c.calibration) {
      for (let i = 10; i < 100; i += 10) {
        grid += `<div class="cal v" style="left:${i}%"><span>${i}</span></div><div class="cal h" style="top:${i}%"><span>${i}</span></div>`;
      }
    }
    const ages = Object.values(c.nodes).map((n) => n.entity && hass.states[n.entity] && Date.parse(hass.states[n.entity].last_updated)).filter((t) => Number.isFinite(t));
    const age = ages.length ? Math.max(0, Math.round((Date.now() - Math.max(...ages)) / 1000)) : null;
    const ia = c.image_area;
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .stage { position: relative; width: 100%; aspect-ratio: ${c.aspect_ratio}; container-type: inline-size; }
        .house { position: absolute; left: ${ia.x}%; top: ${ia.y}%; width: ${ia.w}%; height: auto; pointer-events: none; user-select: none; }
        svg.lines { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
        .flow, .pulse, .idle, .arrow { fill: none; vector-effect: non-scaling-stroke; stroke-linejoin: round; stroke-linecap: round; }
        .flow { stroke: var(--uc-green); stroke-width: 3; }
        .arrow { stroke: var(--uc-green); stroke-width: 3; }
        .pulse { stroke: #D9FFE9; stroke-width: 3; stroke-dasharray: 2 16; animation: flow 1.2s linear infinite; }
        .idle { stroke: #C9CED6; stroke-width: 3; stroke-dasharray: 10 8; opacity: .8; }
        @keyframes flow { to { stroke-dashoffset: -36; } }
        .ball { position: absolute; transform: translate(-50%, -50%); width: 11.6cqw; height: 11.6cqw; box-sizing: border-box; border-radius: 50%; border: .65cqw solid #B9C2CC; padding: 0; background: radial-gradient(circle at 38% 30%, #FFFFFF 0%, #DDE2E8 55%, #A9B3BE 100%); box-shadow: inset 0 -4px 8px rgba(0,0,0,0.18); display: flex; flex-direction: column; align-items: center; justify-content: center; color: #133960; font: 800 max(9px, 2.1cqw) var(--uc-font); line-height: 1.05; cursor: pointer; }
        .ball.solar { width: 13.5cqw; height: 13.5cqw; }
        .ball.grid { width: 12.2cqw; height: 12.2cqw; }
        .ball.on { border-color: var(--uc-green); box-shadow: 0 0 2.6cqw rgba(46,204,113,0.6), inset 0 -4px 8px rgba(0,0,0,0.18); }
        .ball.na { opacity: .6; }
        .ball .val { font-size: max(11px, 3cqw); }
        .det { position: absolute; transform: translateY(-50%); font-size: max(10px, 2.2cqw); line-height: 1.35; white-space: nowrap; text-shadow: 0 1px 3px #000; }
        .det.right { margin-left: 7.5cqw; }
        .det.left { transform: translate(-100%, -50%); margin-left: -8.2cqw; text-align: right; }
        .inv { position: absolute; left: ${inv.x}%; top: ${inv.y}%; transform: translate(-50%, -50%); width: 15.4cqw; height: 9cqw; box-sizing: border-box; border: 2px solid #2F80ED; border-radius: 4px; background: linear-gradient(180deg, #0F3470 0%, #0A2450 100%); box-shadow: 0 0 3.5cqw rgba(47,128,237,0.6); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .3cqw; color: #CFE6FF; font-size: 1.8cqw; letter-spacing: 1px; }
        .inv svg { width: 7cqw; height: auto; }
        .bat { position: absolute; left: ${bat.x}%; top: ${bat.y}%; transform: translate(-2.6cqw, 7.6cqw); display: flex; align-items: flex-end; gap: 1.6cqw; color: var(--uc-text); background: none; border: 0; padding: 0; font: inherit; cursor: pointer; }
        .bat .cell { position: relative; width: 5.1cqw; height: 6.4cqw; box-sizing: border-box; border: 2px solid #3A8EEA; border-radius: 3px; background: rgba(10,36,80,0.7); box-shadow: 0 0 1.6cqw rgba(58,142,234,0.5); }
        .bat .cell::before { content: ''; position: absolute; left: 30%; top: -.9cqw; width: 40%; height: .6cqw; background: #3A8EEA; }
        .bat .fill { position: absolute; left: 3px; right: 3px; bottom: 3px; background: var(--uc-green); }
        .bat .txt { display: flex; flex-direction: column; align-items: center; font-size: max(10px, 2.4cqw); line-height: 1.2; text-shadow: 0 1px 3px #000; }
        .bulb { position: absolute; left: ${home.x}%; top: ${home.y}%; transform: translate(-50%, 6.6cqw); width: 6.4cqw; height: auto; filter: drop-shadow(0 0 1.3cqw rgba(255,196,64,${flows.home.dir ? '0.8' : '0.15'})); opacity: ${flows.home.dir ? 1 : 0.5}; }
        .live { position: absolute; left: .6%; top: .4%; display: flex; align-items: center; gap: 6px; font-size: max(11px, 1.8cqw); color: var(--uc-value); }
        .live i { width: 7px; height: 7px; border-radius: 50%; background: #2ED198; animation: pulse 1.6s ease-in-out infinite; }
        @keyframes pulse { 50% { opacity: .3; } }
        .glow { position: absolute; left: 37%; bottom: -7px; width: 26%; height: 4px; border-radius: 2px; background: #22E0F0; box-shadow: 0 0 14px #22E0F0, 0 0 4px #FFFFFF; animation: bar 2.4s ease-in-out infinite; }
        @keyframes bar { 50% { opacity: .55; } }
        .cal { position: absolute; background: rgba(255,80,80,.45); pointer-events: none; }
        .cal.v { top: 0; bottom: 0; width: 1px; }
        .cal.h { left: 0; right: 0; height: 1px; }
        .cal span { position: absolute; font: 11px monospace; color: #FF8080; left: 2px; top: 2px; }
      </style>
      <div class="stage" role="group" aria-label="Flux d'énergie en direct">
        <img class="house" src="${esc(c.image)}" alt="">
        <svg class="lines" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${paths}</svg>
        <div class="inv" aria-hidden="true"><svg viewBox="0 0 44 26" fill="none" stroke="#8FD3FF" stroke-width="2" stroke-linecap="round"><rect x="2" y="2" width="40" height="22" rx="3"/><path d="M9 13c2-5 4-5 6 0s4 5 6 0 4-5 6 0 4 5 6 0"/></svg><span>${esc(inv.label || 'Onduleur')}</span></div>
        ${nodeHtml('solar', 'solar', c.nodes.solar.label)}
        ${nodeHtml('grid', 'grid', c.nodes.grid.label)}
        ${nodeHtml('battery', 'battery', c.nodes.battery.label || '')}
        ${nodeHtml('home', 'home', '')}
        <button type="button" class="bat" data-entity="${esc(bat.soc_entity || '')}" aria-label="${esc('Batterie à ' + (soc === null ? '—' : Math.round(soc)) + ' %, ' + batState)}">
          <span class="cell"><span class="fill" style="height:${soc === null ? 0 : Math.max(6, Math.min(100, soc)) * 0.86}%"></span></span>
          <span class="txt">${soc === null ? '—' : esc(ucNumber(hass, Math.round(soc), 0))} %<span>${batState}</span></span>
        </button>
        <svg class="bulb" viewBox="0 0 24 26" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4a6 6 0 0 0-4 10.5c.8.8 1 1.6 1 2.5h6c0-.9.2-1.7 1-2.5A6 6 0 0 0 12 4z" fill="#FFC440" stroke="#FFB020" stroke-width="1"/><path d="M9.5 19h5M10 21.5h4" stroke="#9AA6BE" stroke-width="1.6"/><path d="M3 5l2 1.5M21 5l-2 1.5M1.5 11.5h2.5M20 11.5h2.5M5 18l1.6-1.2M19 18l-1.6-1.2" stroke="#FFC440" stroke-width="1.4"/></svg>
        <div class="live"><i></i>${age === null ? 'en attente des mesures' : `en direct · relevé il y a ${age < 120 ? age + ' s' : Math.round(age / 60) + ' min'}`}</div>
        <div class="glow" aria-hidden="true"></div>
        ${grid}
      </div>`;
    this.shadowRoot.querySelectorAll('[data-entity]').forEach((el) => el.addEventListener('click', () => ucMoreInfo(this, el.dataset.entity)));
  }
}

/* ------------------------------------------------------------------ anneau de charge */

class UcanessSocCard extends HTMLElement {
  setConfig(config) {
    this._config = Object.assign({
      soc_entity: 'sensor.uhome_soc',
      power_entity: 'sensor.uhome_puissance_batterie',
      floor_entity: 'input_number.jarvis_batterie_plancher',
      capacity_entity: 'input_number.jarvis_batterie_capacite',
    }, config || {});
    this._ucSeen = null;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const c = this._config;
    if (ucChanged(this, hass, [c.soc_entity, c.power_entity, c.floor_entity, c.capacity_entity].filter(Boolean))) this._render();
  }

  getCardSize() { return 6; }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    const c = this._config;
    const hass = this._hass || { states: {} };
    const soc = ucNum(hass, c.soc_entity);
    const p = ucWatts(hass, c.power_entity);
    const floor = c.floor !== undefined ? c.floor : ucNum(hass, c.floor_entity);
    const cap = c.capacity !== undefined ? c.capacity : ucNum(hass, c.capacity_entity);
    const R = 88, C = 2 * Math.PI * R;
    const dash = soc === null ? 0 : C * Math.max(0, Math.min(100, soc)) / 100;
    const state = p === null || Math.abs(p) < 30 ? 'Veille' : p > 0 ? 'Chargement' : 'Décharge';
    const stored = soc !== null && cap ? ucNumber(hass, cap * soc / 100, 2) + ' kWh' : '—';
    const avail = soc !== null && cap && floor !== null ? ucNumber(hass, Math.max(0, cap * (soc - floor) / 100), 2) + ' kWh' : '—';
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .wrap { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 8px 0; }
        .ring { position: relative; width: min(250px, 100%); aspect-ratio: 1; }
        .ring svg { width: 100%; height: 100%; }
        .arc { animation: draw 1.2s ease-out both; filter: drop-shadow(0 0 6px rgba(46,204,113,0.7)); }
        @keyframes draw { from { stroke-dasharray: 0 ${C.toFixed(1)}; } }
        .mid { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; text-align: center; }
        .mid small { font-size: 13px; color: var(--uc-muted); letter-spacing: 2px; }
        .mid b { font: 700 clamp(36px, 10vw, 62px) var(--uc-font); line-height: 1; }
        .mid span { font-size: 15px; color: #2ED198; }
        .mid em { font-style: normal; font-size: 13px; color: var(--uc-muted); }
        .row { display: flex; gap: 22px; font-size: 13px; }
        .row span span { color: var(--uc-value); }
        .row span.warn span { color: var(--uc-orange); }
      </style>
      <div class="wrap">
        <div class="ring">
          <svg viewBox="0 0 250 250" role="img" aria-label="Charge de la batterie : ${soc === null ? 'indisponible' : Math.round(soc) + ' %'}">
            <circle cx="125" cy="125" r="104" fill="none" stroke="#12345E" stroke-width="2" stroke-dasharray="3 6"/>
            <circle cx="125" cy="125" r="${R}" fill="none" stroke="#16365F" stroke-width="20"/>
            <circle class="arc" cx="125" cy="125" r="${R}" fill="none" stroke="#2ECC71" stroke-width="20" stroke-dasharray="${dash.toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 125 125)"/>
          </svg>
          <div class="mid"><small>CHARGE</small><b>${soc === null ? '—' : esc(ucNumber(hass, Math.round(soc), 0))} %</b><span>${state}${p !== null && Math.abs(p) >= 30 ? ' · ' + esc(ucNumber(hass, Math.abs(p) / 1000, 2)) + ' kW' : ''}</span>${floor !== null ? `<em>plancher ${esc(ucNumber(hass, floor, 0))} %${cap ? ' · ' + esc(ucNumber(hass, cap, 1)) + ' kWh' : ''}</em>` : ''}</div>
        </div>
        <div class="row"><span>Stockée <span>${esc(stored)}</span></span><span class="warn">Avant plancher <span>${esc(avail)}</span></span></div>
      </div>`;
  }
}

/* ------------------------------------------------------------------ texte repliable */

/*
 * custom:ucaness-note-card : un texte (carte markdown) replié sur quelques lignes, terminé par « … ».
 * Un appui sur le texte ou sur « … » le déplie en entier ; un nouvel appui le replie.
 * Remplace directement une carte markdown : changer « type: markdown » en
 * « type: custom:ucaness-note-card » et garder « content: ». Option « lines » (4 par défaut),
 * « mobile_lines » sous 900 px de large (par défaut la même valeur), ou « card » pour une autre carte.
 */
class UcanessNoteCard extends HTMLElement {
  setConfig(config) {
    if (!config || (!config.content && !config.card)) {
      throw new Error('ucaness-note-card : indiquez « content » (texte markdown) ou « card ».');
    }
    this._config = Object.assign({ lines: 4 }, config);
    this._open = false;
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    this._build();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._child) this._child.hass = hass;
  }

  getCardSize() { return Math.ceil((this._lines() * 21 + 16) / 50); }

  disconnectedCallback() {
    if (this._ro) this._ro.disconnect();
    if (this._onResize) window.removeEventListener('resize', this._onResize);
  }

  connectedCallback() {
    const slot = this.shadowRoot && this.shadowRoot.querySelector('.slot');
    if (this._ro && slot) this._ro.observe(slot);
    if (this._onResize) window.addEventListener('resize', this._onResize);
  }

  _lines() {
    const c = this._config || {};
    const mobile = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(max-width: 900px)').matches;
    return Math.max(1, Number(mobile && c.mobile_lines ? c.mobile_lines : c.lines) || 4);
  }

  async _build() {
    // Home Assistant peut rappeler setConfig avant la fin de la construction précédente :
    // seule la dernière construction est gardée, et l'ancienne surveillance de taille est arrêtée.
    const build = (this._buildId = (this._buildId || 0) + 1);
    if (this._ro) { this._ro.disconnect(); this._ro = null; }
    if (this._onResize) { window.removeEventListener('resize', this._onResize); this._onResize = null; }
    const c = this._config;
    const childConf = c.card || Object.assign({ type: 'markdown' }, c.content !== undefined ? { content: c.content } : {});
    this.shadowRoot.innerHTML = `
      <style>${UC_BASE_CSS}
        :host { display: block; }
        .clip { position: relative; overflow: hidden; cursor: pointer; border-radius: 0; }
        .slot { display: flow-root; }
        .clip.open { cursor: auto; }
        .fade { position: absolute; left: 0; right: 0; bottom: 0; height: 2.4em; background: linear-gradient(180deg, rgba(22,40,72,0) 0%, rgba(22,40,72,0.96) 78%); pointer-events: none; }
        .more { position: absolute; right: 6px; bottom: 2px; min-width: 44px; height: 32px; padding: 0 10px; border: 1px solid var(--uc-tab-border); border-radius: 4px; background: #0A2546; color: var(--uc-tab); font: 700 16px var(--uc-font); letter-spacing: 1px; cursor: pointer; }
        .less { display: block; margin: 2px 6px 6px auto; min-width: 44px; height: 32px; padding: 0 10px; border: 1px solid var(--uc-tab-border); border-radius: 4px; background: #0A2546; color: var(--uc-tab); font: 400 14px var(--uc-font); cursor: pointer; }
        .clip:not(.cut) .fade, .clip:not(.cut) .more, .clip.open .fade, .clip.open .more { display: none; }
        .less[hidden] { display: none; }
      </style>
      <div class="clip" part="clip"><div class="slot"></div><div class="fade" aria-hidden="true"></div><button type="button" class="more" aria-expanded="false" aria-label="Lire la suite">…</button></div>
      <button type="button" class="less" aria-expanded="true" hidden>Réduire</button>`;
    const clip = this.shadowRoot.querySelector('.clip');
    const more = this.shadowRoot.querySelector('.more');
    const less = this.shadowRoot.querySelector('.less');
    const [child] = await ucCreateCards([childConf], this._hass, this);
    if (build !== this._buildId) return;
    this._child = child;
    child.style.display = 'block';
    this.shadowRoot.querySelector('.slot').appendChild(child);
    const toggle = (open) => {
      this._open = open;
      clip.classList.toggle('open', open);
      clip.style.maxHeight = open ? 'none' : `${this._lines() * 21 + 16}px`;
      more.setAttribute('aria-expanded', String(open));
      less.hidden = !open || !clip.classList.contains('cut');
    };
    const slot = this.shadowRoot.querySelector('.slot');
    // La hauteur se mesure sur le conteneur : une carte de Home Assistant est un élément « en ligne »
    // dont la hauteur propre vaut 0.
    const measure = () => {
      const limit = this._lines() * 21 + 16;
      clip.classList.toggle('cut', slot.scrollHeight > limit + 4);
      toggle(this._open);
    };
    clip.addEventListener('click', (ev) => {
      if (!clip.classList.contains('cut') || this._open) return;
      // Un lien reste un lien. Il est dans le shadow DOM de la carte markdown : on suit le chemin complet de l'appui.
      if (ev.composedPath().some((el) => el.tagName === 'A')) return;
      toggle(true);
    });
    more.addEventListener('click', (ev) => { ev.stopPropagation(); toggle(true); });
    less.addEventListener('click', () => toggle(false));
    if (typeof ResizeObserver !== 'undefined') {
      this._ro = new ResizeObserver(measure);
      this._ro.observe(slot);
    }
    this._onResize = measure;
    window.addEventListener('resize', this._onResize);
    measure();
  }
}

/* ------------------------------------------------------------------ enregistrement */

const UC_CARDS = [
  ['ucaness-layout-card', UcanessLayoutCard, 'UCANESS : mise en page', 'En-tête et colonnes du tableau de bord UCANESS HOME ASSISTANT.'],
  ['ucaness-header-card', UcanessHeaderCard, 'UCANESS : en-tête', 'Bandeau titre, onglets, heure, liaison et alertes.'],
  ['ucaness-panel-card', UcanessPanelCard, 'UCANESS : panneau', 'Panneau titré dans le style UCANESS, avec carrousel ou onglets facultatifs.'],
  ['ucaness-flow-card', UcanessFlowCard, 'UCANESS : maison en direct', 'Flux solaire, réseau, batterie et maison sur l’image de votre maison.'],
  ['ucaness-note-card', UcanessNoteCard, 'UCANESS : texte repliable', 'Texte replié sur quelques lignes, déplié d’un appui.'],
  ['ucaness-soc-card', UcanessSocCard, 'UCANESS : charge batterie', 'Anneau de charge, énergie stockée et réserve avant le plancher.'],
];

for (const [tag, cls, name, description] of UC_CARDS) {
  if (!customElements.get(tag)) customElements.define(tag, cls);
  window.customCards = window.customCards || [];
  if (!window.customCards.some((c) => c.type === tag)) {
    window.customCards.push({ type: tag, name, description, preview: false });
  }
}

console.info(`%c UCANESS HOME ASSISTANT %c ${UC_VERSION} `, 'background:#0B4F8F;color:#fff;font-weight:700', 'background:#00D1D6;color:#06203F');

export { UcanessFlowCard, UcanessNoteCard, UcanessPanelCard, UcanessLayoutCard, UcanessHeaderCard, UcanessSocCard, ucWatts, ucNum, ucChanged, UC_LIGHT, UC_VERSION };
