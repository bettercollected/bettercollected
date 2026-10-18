const base = 'http://localhost:3000';
const user = process.env.UMAMI_ADMIN_USER || 'admin';
const oldPw = process.env.UMAMI_OLD_PASSWORD || 'umami';
const newPw = process.env.UMAMI_NEW_PASSWORD || '';
const post = (path, body, token) =>
  fetch(base + path, {
    method: 'POST',
    headers: Object.assign({ 'Content-Type': 'application/json' }, token ? { Authorization: 'Bearer ' + token } : {}),
    body: JSON.stringify(body),
  });
(async () => {
  let r = await post('/api/auth/login', { username: user, password: oldPw });
  if (r.status !== 200) {
    console.log('default_login=no');
    process.exit(3);
  }
  if (!newPw) {
    console.log('default_login=yes');
    process.exit(0);
  }
  const data = await r.json();
  r = await post('/api/users/' + data.user.id, { password: newPw }, data.token);
  if (!r.ok) {
    console.log('change_failed status=' + r.status);
    process.exit(4);
  }
  r = await post('/api/auth/login', { username: user, password: newPw });
  console.log(r.status === 200 ? 'rotated=yes' : 'verify_failed');
  process.exit(r.status === 200 ? 0 : 5);
})().catch(() => {
  console.log('error');
  process.exit(6);
});
