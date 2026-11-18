'use strict';
/* Trang đăng nhập / đăng ký. Kiểm tra dữ liệu ở trình duyệt trước (HTML5 + JS), máy chủ kiểm tra lại lần nữa. */
(() => {
  const fLogin = document.getElementById('form-login');
  const fReg = document.getElementById('form-register');
  const tabL = document.getElementById('tab-login');
  const tabR = document.getElementById('tab-register');
  const msgL = document.getElementById('login-msg');
  const msgR = document.getElementById('register-msg');
  const title = document.getElementById('title');
  const sub = document.getElementById('subtitle');

  function chonTab(dangKy) {
    tabL.classList.toggle('active', !dangKy); tabR.classList.toggle('active', dangKy);
    tabL.setAttribute('aria-selected', String(!dangKy)); tabR.setAttribute('aria-selected', String(dangKy));
    fLogin.classList.toggle('hidden', dangKy); fReg.classList.toggle('hidden', !dangKy);
    title.textContent = dangKy ? 'Tạo tài khoản' : 'Đăng nhập';
    sub.textContent = dangKy ? 'Đăng ký để quản lý container trong bãi.' : 'Dùng tài khoản đã đăng ký để vào hệ thống.';
    (dangKy ? fReg : fLogin).querySelector('input').focus();
  }
  tabL.addEventListener('click', () => chonTab(false));
  tabR.addEventListener('click', () => chonTab(true));

  // Đã đăng nhập rồi thì vào thẳng trang quản lý
  Api.get('/api/auth/me').then(() => location.replace('/containers.html')).catch(() => {});
  loadHost();

  fLogin.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    hideMsg(msgL);
    if (!fLogin.reportValidity()) return;
    const btn = fLogin.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      await Api.post('/api/auth/login', {
        username: fLogin.username.value.trim().toLowerCase(),
        password: fLogin.password.value,
      });
      location.replace('/containers.html');
    } catch (e) {
      showMsg(msgL, e.message);
      fLogin.password.value = '';
      fLogin.password.focus();
    } finally {
      btn.disabled = false;
    }
  });

  const p1 = document.getElementById('r-password');
  const p2 = document.getElementById('r-password2');
  const uname = document.getElementById('r-username');
  function kiemMatKhau() {
    const v = p1.value;
    p1.setCustomValidity(v && !(/[A-Za-z]/.test(v) && /[0-9]/.test(v)) ? 'Mật khẩu phải có cả chữ và số' : '');
    p2.setCustomValidity(p2.value && p2.value !== v ? 'Hai mật khẩu không khớp' : '');
  }
  p1.addEventListener('input', kiemMatKhau);
  p2.addEventListener('input', kiemMatKhau);
  uname.addEventListener('input', () => {
    uname.setCustomValidity(uname.validity.patternMismatch ? 'Chỉ dùng chữ thường không dấu, số, dấu chấm, gạch dưới' : '');
  });

  fReg.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    hideMsg(msgR);
    uname.value = uname.value.trim().toLowerCase();
    kiemMatKhau();
    if (!fReg.reportValidity()) return;
    const btn = fReg.querySelector('button[type=submit]');
    btn.disabled = true;
    try {
      const u = await Api.post('/api/auth/register', {
        full_name: fReg.full_name.value.trim(),
        username: uname.value,
        password: p1.value,
      });
      fReg.reset();
      chonTab(false);
      fLogin.username.value = u.username;
      fLogin.password.focus();
      showMsg(msgL, `Đã tạo tài khoản ${u.username}. Mời đăng nhập.`, 'ok');
    } catch (e) {
      showMsg(msgR, e.message);
    } finally {
      btn.disabled = false;
    }
  });
})();
