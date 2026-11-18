'use strict';
/* Gọi REST API + tiện ích dùng chung.
 * An toàn XSS: mọi dữ liệu từ máy chủ được gắn vào trang bằng textContent (không dùng innerHTML).
 */
const Api = (() => {
  let csrf = null;

  async function req(method, url, body) {
    const opt = { method, headers: { Accept: 'application/json' }, credentials: 'same-origin' };
    if (body !== undefined) {
      opt.headers['Content-Type'] = 'application/json';
      opt.body = JSON.stringify(body);
    }
    if (method !== 'GET' && csrf) opt.headers['X-CSRF-Token'] = csrf;   // chống CSRF
    let res;
    try {
      res = await fetch(url, opt);
    } catch (e) {
      throw Object.assign(new Error('Không kết nối được máy chủ'), { status: 0 });
    }
    let data = null;
    if (res.status !== 204) {
      try { data = await res.json(); } catch { data = null; }
    }
    if (!res.ok) {
      let msg = (data && typeof data.detail === 'string') ? data.detail : `Lỗi ${res.status}`;
      if (res.status === 429 && !(data && data.detail)) msg = 'Thao tác quá nhanh, vui lòng thử lại sau.';
      throw Object.assign(new Error(msg), { status: res.status, data });
    }
    return data;
  }

  return {
    setCsrf: (t) => { csrf = t; },
    get: (u) => req('GET', u),
    post: (u, b) => req('POST', u, b),
    put: (u, b) => req('PUT', u, b),
    del: (u) => req('DELETE', u),
  };
})();

/* ISO 6346: chữ số kiểm tra của số container (giống hệt hàm chu_so_kiem_tra ở backend). */
const ISO_VAL = (() => {
  const v = {}; let n = 10;
  for (const c of 'ABCDEFGHIJKLMNOPQRSTUVWXYZ') { if (n % 11 === 0) n++; v[c] = n++; }
  return v;
})();
function isoCheckDigit(so) {
  let sum = 0;
  for (let i = 0; i < 10; i++) {
    const c = so[i];
    sum += (/[A-Z]/.test(c) ? ISO_VAL[c] : Number(c)) * (2 ** i);
  }
  return sum % 11 % 10;
}
function containerNoError(raw) {
  const so = raw.replace(/\s+/g, '').toUpperCase();
  if (!/^[A-Z]{3}[UJZ][0-9]{7}$/.test(so)) return 'Dạng: 3 chữ + U/J/Z + 7 chữ số (vd CSQU3054383)';
  const cd = isoCheckDigit(so);
  if (cd !== Number(so[10])) return `Sai chữ số kiểm tra, chữ số cuối đúng là ${cd}`;
  return '';
}

/* Tạo phần tử DOM an toàn: el('td', {class: 'x'}, 'văn bản', childNode) */
function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'dataset') Object.assign(e.dataset, v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children) {
    if (c === null || c === undefined) continue;
    e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return e;
}

function toast(msg, type = 'ok') {
  const box = document.getElementById('toasts');
  if (!box) return;
  const t = el('div', { class: 'toast' + (type === 'err' ? ' err' : '') }, msg);
  box.append(t);
  setTimeout(() => t.remove(), 3800);
}

function showMsg(box, text, kind = 'error') {
  box.textContent = text;
  box.className = kind === 'ok' ? 'form-ok' : 'form-error';
}
function hideMsg(box) { box.className = 'hidden'; box.textContent = ''; }

async function loadHost() {
  try {
    const m = await Api.get('/api/meta');
    const h = document.getElementById('host');
    if (h) h.textContent = m.host;
    return m;
  } catch { return null; }
}
