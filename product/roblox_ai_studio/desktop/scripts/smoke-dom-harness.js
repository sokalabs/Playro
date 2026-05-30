'use strict';

/**
 * Minimal DOM harness for headless renderer smokes (vm.runInContext).
 * Supports sidebar/handoff parsing and chat message bubble parsing.
 */

class Element {
  constructor(tagName, document) {
    this.tagName = tagName.toUpperCase();
    this.document = document;
    this.children = [];
    this.classList = { add() {}, remove() {} };
    this.eventListeners = {};
    this.attributes = {};
    this.value = '';
    this.id = '';
    this.className = '';
    this.dataset = {};
    this.disabled = false;
    this.textContent = '';
    this.scrollTop = 0;
    this.scrollHeight = 0;
  }
  appendChild(child) { this.children.push(child); return child; }
  remove() { this.removed = true; }
  addEventListener(type, fn) { (this.eventListeners[type] ||= []).push(fn); }
  click() { (this.eventListeners.click || []).forEach(fn => fn({ target: this, preventDefault() {} })); }
  focus() { this.document.activeElement = this; }
  scrollIntoView() {}
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === 'id') this.id = String(value);
  }
  get innerText() { return this.textContent || this.children.map(child => child.innerText || '').join(' '); }
  set innerHTML(html) { this.document.setHTML(this, html); }
  get innerHTML() { return this._html || ''; }
}

class FakeDocument {
  constructor(options = {}) {
    this.parseMode = options.parseMode || 'sidebar';
    this.elementsById = {};
    this.elements = [];
    this.body = new Element('body', this);
    this.activeElement = null;
    this.eventListeners = {};
    this.userMessages = [];
    this.aiMessages = [];
  }
  createElement(tagName) {
    const el = new Element(tagName, this);
    if (this.parseMode === 'sidebar') this.elements.push(el);
    return el;
  }
  addEventListener(type, fn) { (this.eventListeners[type] ||= []).push(fn); }
  dispatchEvent(event) { (this.eventListeners[event.type] || []).forEach(fn => fn(event)); }
  getElementById(id) { return this.elementsById[id] || null; }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    if (selector === '[data-sidebar-panel]') return this.elements.filter(el => el.dataset.sidebarPanel);
    if (selector === '[data-action]') return this.elements.filter(el => el.dataset.action);
    if (selector === '[data-skill]') return this.elements.filter(el => el.dataset.skill);
    if (selector === '[data-quality]') return this.elements.filter(el => el.dataset.quality);
    if (selector === '[data-resume-build]') return this.elements.filter(el => el.dataset.resumeBuild);
    if (selector === '[data-open-detail]') return this.elements.filter(el => el.dataset.openDetail);
    if (selector === '[data-open-advanced-panel]') return this.elements.filter(el => el.dataset.openAdvancedPanel);
    if (selector === '[data-skill-pack]') return this.elements.filter(el => el.dataset.skillPack);
    if (selector === '.chip') return this.elements.filter(el => el.dataset.genre);
    if (selector === '.copy-btn') return [];
    if (selector === '.message.user-msg .bubble') return this.userMessages || [];
    if (selector === '.message.ai-msg .bubble') return this.aiMessages || [];
    return [];
  }
  setHTML(element, html) {
    element._html = html;
    if (this.parseMode === 'messages') {
      this._setHTMLMessages(element, html);
      return;
    }
    this._setHTMLSidebar(element, html);
  }
  _setHTMLSidebar(element, html) {
    this.elementsById = { app: this.elementsById.app };
    this.elements = [];
    const tagRe = /<([a-z]+)([^>]*)>/gi;
    let match;
    while ((match = tagRe.exec(html))) {
      const [, tag, attrs] = match;
      const el = new Element(tag, this);
      el.disabled = /\sdisabled(?:\s|>|=)/.test(attrs);
      const id = /\sid="([^"]+)"/.exec(attrs)?.[1];
      if (id) { el.id = id; this.elementsById[id] = el; }
      const cls = /\sclass="([^"]+)"/.exec(attrs)?.[1];
      if (cls) el.className = cls;
      for (const dm of attrs.matchAll(/\sdata-([a-z0-9-]+)="([^"]*)"/gi)) {
        const key = dm[1].replace(/-([a-z])/g, (_, c) => c.toUpperCase());
        el.dataset[key] = decodeHtml(dm[2]);
      }
      this.elements.push(el);
    }
  }
  _setHTMLMessages(element, html) {
    this.elementsById = {};
    this.userMessages = [];
    this.aiMessages = [];
    const idRe = /<([a-z]+)([^>]*\sid="([^"]+)"[^>]*)[^>]*>([\s\S]*?)(?:<\/\1>|$)/gi;
    let match;
    while ((match = idRe.exec(html))) {
      const [, tag, attrs, id] = match;
      const el = new Element(tag, this);
      el.id = id;
      el.disabled = /\sdisabled(?:\s|>|=)/.test(attrs);
      this.elementsById[id] = el;
    }
    const userRe = /<article class="message user-msg">[\s\S]*?<div class="bubble">([\s\S]*?)<\/div>[\s\S]*?<\/article>/gi;
    while ((match = userRe.exec(html))) {
      this.userMessages.push({ textContent: decodeHtml(match[1]), innerText: decodeHtml(match[1]) });
    }
    const aiRe = /<article class="message ai-msg[^"]*">[\s\S]*?<div class="bubble[^"]*">([\s\S]*?)<\/div>[\s\S]*?<\/article>/gi;
    while ((match = aiRe.exec(html))) {
      const text = decodeHtml(match[1]).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
      this.aiMessages.push({ textContent: text, innerText: text });
    }
  }
}

function decodeHtml(text) {
  return String(text)
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function createAppRoot(document) {
  const app = new Element('div', document);
  app.id = 'app';
  document.elementsById.app = app;
  document.getElementById = (id) => (id === 'app' ? app : (document.elementsById[id] || null));
  return app;
}

function bindWindowGlobals(context) {
  const windowObj = context.window;
  windowObj.document = context.document;
  windowObj.window = windowObj;
  windowObj.navigator = context.navigator;
  windowObj.console = context.console;
  windowObj.setTimeout = context.setTimeout;
  windowObj.clearTimeout = context.clearTimeout;
  windowObj.EventSource = context.EventSource;
  windowObj.fetch = context.fetch;
  context.global = context;
  return context;
}

module.exports = {
  Element,
  FakeDocument,
  decodeHtml,
  createAppRoot,
  bindWindowGlobals,
};
