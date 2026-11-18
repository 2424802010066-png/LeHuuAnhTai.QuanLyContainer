'use strict';
/* Trang quản lý container: xem (tìm kiếm, lọc, phân trang) – thêm – sửa – xóa. */
(() => {
  const S = { page: 1, page_size: 10, q: '', trang_thai: '', loai: '' };
  let META = { loai: {}, trang_thai: {} };
  let dangSua = null;      // id container đang sửa (null = thêm mới)
  let canXoa = null;       // container đang chờ xác nhận xóa

  const $ = (id) => document.getElementById(id);
  const rows = $('rows');
  const dlg = $('dlg-form');
  const form = $('form-cont');
  const dlgDel = $('dlg-delete');
  const formMsg = $('form-msg');

  const fmtSo = new Intl.NumberFormat('vi-VN');
  const fmtNgay = (s) => (s ? s.split('-').reverse().join('/') : '');
  const homNay = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };

  function loiPhien(e) {
    if (e.status === 401) { location.replace('/'); return true; }
    return false;
  }

  /* ---------------- khởi tạo ---------------- */
  async function init() {
    try {
      const me = await Api.get('/api/auth/me');
      Api.setCsrf(me.csrf_token);
      $('user-name').textContent = me.user.full_name;
    } catch (e) {
      location.replace('/');
      return;
    }
    META = (await loadHost()) || META;
    for (const [k, v] of Object.entries(META.trang_thai)) {
      $('f-trang-thai').append(el('option', { value: k }, v));
      $('c-trang-thai').append(el('option', { value: k }, v));
      $('stats').append(el('div', { class: `stat s-${k}` },
        el('div', { class: 'label' }, v), el('div', { class: 'value', id: `st-${k}` }, '–')));
    }
    for (const [k, v] of Object.entries(META.loai)) {
      $('f-loai').append(el('option', { value: k }, `${k} – ${v}`));
      $('c-loai').append(el('option', { value: k }, `${k} – ${v}`));
    }
    $('c-ngay').max = homNay();
    await Promise.all([taiDanhSach(), taiThongKe()]);
  }

  /* ---------------- danh sách ---------------- */
  async function taiDanhSach() {
    const p = new URLSearchParams({ page: S.page, page_size: S.page_size });
    if (S.q) p.set('q', S.q);
    if (S.trang_thai) p.set('trang_thai', S.trang_thai);
    if (S.loai) p.set('loai', S.loai);
    let data;
    try {
      data = await Api.get('/api/containers?' + p.toString());
    } catch (e) {
      if (!loiPhien(e)) toast(e.message, 'err');
      return;
    }
    if (data.items.length === 0 && S.page > 1) { S.page = data.pages; return taiDanhSach(); }
    rows.replaceChildren();
    if (data.items.length === 0) {
      rows.append(el('tr', {}, el('td', { class: 'empty', colspan: 8 },
        S.q || S.trang_thai || S.loai ? 'Không có container nào khớp bộ lọc.' : 'Chưa có container nào. Bấm “+ Thêm container” để bắt đầu.')));
    }
    for (const c of data.items) {
      rows.append(el('tr', {},
        el('td', {}, el('span', { class: 'so-cont mono' }, c.so_container)),
        el('td', { class: 'chu-hang' }, c.chu_hang),
        el('td', {}, el('span', { class: 'loai', title: META.loai[c.loai] || '' }, c.loai)),
        el('td', {}, el('span', { class: `badge ${c.trang_thai}` }, META.trang_thai[c.trang_thai] || c.trang_thai)),
        el('td', { class: 'mono' }, c.vi_tri_bai || '—'),
        el('td', { class: 'num' }, c.trong_luong_kg == null ? '—' : fmtSo.format(c.trong_luong_kg)),
        el('td', {}, fmtNgay(c.ngay_nhap) || '—'),
        el('td', { class: 'actions' },
          el('button', { class: 'btn btn-ghost btn-sm', type: 'button', dataset: { act: 'sua', id: c.id } }, 'Sửa'),
          el('button', { class: 'btn btn-ghost btn-sm', type: 'button', dataset: { act: 'xoa', id: c.id, so: c.so_container } }, 'Xóa'))));
    }
    const tu = data.total === 0 ? 0 : (data.page - 1) * data.page_size + 1;
    const den = Math.min(data.page * data.page_size, data.total);
    $('pager-info').textContent = `Hiển thị ${tu}–${den} / ${data.total} container`;
    veTrang(data.page, data.pages);
  }

  function veTrang(page, pages) {
    const box = $('pages');
    box.replaceChildren();
    const nut = (label, p, opts = {}) => el('button', {
      class: 'btn btn-ghost btn-sm' + (opts.current ? ' current' : ''), type: 'button',
      disabled: opts.disabled || false, dataset: { page: p }, 'aria-label': opts.aria || null,
    }, label);
    box.append(nut('‹', page - 1, { disabled: page <= 1, aria: 'Trang trước' }));
    let bd = Math.max(1, page - 3);
    const kt = Math.min(pages, bd + 6);
    bd = Math.max(1, kt - 6);
    for (let i = bd; i <= kt; i++) box.append(nut(String(i), i, { current: i === page }));
    box.append(nut('›', page + 1, { disabled: page >= pages, aria: 'Trang sau' }));
  }

  async function taiThongKe() {
    try {
      const t = await Api.get('/api/containers/thong-ke');
      $('st-tong').textContent = fmtSo.format(t.tong);
      for (const [k, v] of Object.entries(t.theo_trang_thai)) {
        const o = $(`st-${k}`);
        if (o) o.textContent = fmtSo.format(v);
      }
    } catch (e) { loiPhien(e); }
  }
  const taiLai = () => Promise.all([taiDanhSach(), taiThongKe()]);

  /* ---------------- bộ lọc ---------------- */
  let hen;
  $('q').addEventListener('input', () => {
    clearTimeout(hen);
    hen = setTimeout(() => { S.q = $('q').value.trim(); S.page = 1; taiDanhSach(); }, 300);
  });
  $('f-trang-thai').addEventListener('change', (e) => { S.trang_thai = e.target.value; S.page = 1; taiDanhSach(); });
  $('f-loai').addEventListener('change', (e) => { S.loai = e.target.value; S.page = 1; taiDanhSach(); });
  $('pages').addEventListener('click', (e) => {
    const b = e.target.closest('button[data-page]');
    if (!b || b.disabled) return;
    S.page = Number(b.dataset.page);
    taiDanhSach();
  });

  /* ---------------- thêm / sửa ---------------- */
  function xoaLoi() {
    hideMsg(formMsg);
    form.querySelectorAll('[data-err]').forEach((s) => { s.textContent = ''; });
    form.querySelectorAll('.field.has-error').forEach((f) => f.classList.remove('has-error'));
  }
  function datLoi(field, msg) {
    const s = form.querySelector(`[data-err="${field}"]`);
    if (s) { s.textContent = msg; s.closest('.field').classList.add('has-error'); }
  }
  function capNhatViTriBatBuoc() {
    const bat = $('c-trang-thai').value === 'TRONG_BAI';
    $('c-vi-tri').required = bat;
    $('vi-tri-req').classList.toggle('hidden', !bat);
  }
  $('c-trang-thai').addEventListener('change', capNhatViTriBatBuoc);
  $('c-so').addEventListener('input', () => {
    const v = $('c-so').value;
    $('c-so').setCustomValidity(v.length >= 11 ? containerNoError(v) : '');
  });

  function moForm(c = null) {
    dangSua = c ? c.id : null;
    form.reset();
    xoaLoi();
    $('dlg-title').textContent = c ? `Sửa container ${c.so_container}` : 'Thêm container';
    $('c-so').value = c ? c.so_container : '';
    $('c-chu-hang').value = c ? c.chu_hang : '';
    $('c-loai').value = c ? c.loai : '20GP';
    $('c-trang-thai').value = c ? c.trang_thai : 'TRONG_BAI';
    $('c-vi-tri').value = c && c.vi_tri_bai ? c.vi_tri_bai : '';
    $('c-trong-luong').value = c && c.trong_luong_kg != null ? c.trong_luong_kg : '';
    $('c-ngay').value = c ? (c.ngay_nhap || '') : homNay();
    $('c-ghi-chu').value = c && c.ghi_chu ? c.ghi_chu : '';
    capNhatViTriBatBuoc();
    dlg.showModal();
    $('c-so').focus();
  }

  function kiemTraForm() {
    xoaLoi();
    let ok = true;
    const so = $('c-so');
    so.value = so.value.replace(/\s+/g, '').toUpperCase();
    so.setCustomValidity(containerNoError(so.value));
    $('c-vi-tri').value = $('c-vi-tri').value.trim().toUpperCase();
    for (const inp of form.querySelectorAll('input, select, textarea')) {
      if (!inp.checkValidity()) {
        ok = false;
        datLoi(inp.name, inp.validationMessage);
      }
    }
    return ok;
  }

  $('btn-add').addEventListener('click', () => moForm());
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (!kiemTraForm()) { form.querySelector('.has-error input, .has-error select')?.focus(); return; }
    const tl = $('c-trong-luong').value;
    const body = {
      so_container: $('c-so').value,
      chu_hang: $('c-chu-hang').value.trim(),
      loai: $('c-loai').value,
      trang_thai: $('c-trang-thai').value,
      vi_tri_bai: $('c-vi-tri').value || null,
      trong_luong_kg: tl === '' ? null : Number(tl),
      ngay_nhap: $('c-ngay').value || null,
      ghi_chu: $('c-ghi-chu').value.trim() || null,
    };
    const btn = $('btn-save');
    btn.disabled = true;
    try {
      if (dangSua) await Api.put(`/api/containers/${dangSua}`, body);
      else await Api.post('/api/containers', body);
      dlg.close();
      toast(dangSua ? `Đã cập nhật ${body.so_container}` : `Đã thêm ${body.so_container}`);
      if (!dangSua) S.page = 1;
      await taiLai();
    } catch (e) {
      if (loiPhien(e)) return;
      if (e.data && e.data.errors) {
        for (const [k, v] of Object.entries(e.data.errors)) datLoi(k, v);
      }
      showMsg(formMsg, e.message);
    } finally {
      btn.disabled = false;
    }
  });

  /* ---------------- sửa / xóa từ bảng ---------------- */
  rows.addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-act]');
    if (!b) return;
    if (b.dataset.act === 'sua') {
      try {
        moForm(await Api.get(`/api/containers/${b.dataset.id}`));
      } catch (err) {
        if (!loiPhien(err)) toast(err.message, 'err');
      }
    } else {
      canXoa = { id: b.dataset.id, so: b.dataset.so };
      $('del-so').textContent = canXoa.so;
      dlgDel.showModal();
    }
  });
  $('btn-del-ok').addEventListener('click', async () => {
    if (!canXoa) return;
    try {
      await Api.del(`/api/containers/${canXoa.id}`);
      toast(`Đã xóa ${canXoa.so}`);
      dlgDel.close();
      await taiLai();
    } catch (e) {
      if (!loiPhien(e)) toast(e.message, 'err');
    }
  });

  document.querySelectorAll('[data-close]').forEach((b) =>
    b.addEventListener('click', () => b.closest('dialog').close()));

  $('btn-logout').addEventListener('click', async () => {
    try { await Api.post('/api/auth/logout'); } catch { /* phiên đã hết hạn thì vẫn quay về trang đăng nhập */ }
    location.replace('/');
  });

  init();
})();
