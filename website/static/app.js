// Image preview and a saved color-theme preference. Database work stays on the server.
const themeButton = document.querySelector('.theme-toggle');
function setTheme(dark) {
  document.body.classList.toggle('dark', dark);
  if (themeButton) themeButton.textContent = dark ? 'Light mode' : 'Dark mode';
}
try { setTheme(localStorage.getItem('reading-room-theme') === 'dark'); } catch (_) {}
themeButton?.addEventListener('click', () => {
  const dark = !document.body.classList.contains('dark');
  setTheme(dark);
  try { localStorage.setItem('reading-room-theme', dark ? 'dark' : 'light'); } catch (_) {}
});
const imageInput = document.querySelector('[data-image-input]');
const preview = document.querySelector('[data-image-preview]');
let previewUrl;
imageInput?.addEventListener('change', () => {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  const file = imageInput.files[0];
  if (file && file.type.startsWith('image/')) {
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    preview.classList.remove('hidden');
  }
});
