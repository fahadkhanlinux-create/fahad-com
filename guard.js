(function () {
  var block = function (e) { e.preventDefault(); return false; };
  ['contextmenu', 'copy', 'cut', 'dragstart', 'selectstart'].forEach(function (ev) {
    document.addEventListener(ev, block);
  });
  document.addEventListener('keydown', function (e) {
    var k = (e.key || '').toLowerCase();
    if (e.key === 'F12' ||
        ((e.ctrlKey || e.metaKey) && (k === 'u' || k === 's' || k === 'p')) ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && ['i', 'j', 'c', 'k'].indexOf(k) !== -1)) {
      e.preventDefault(); e.stopPropagation(); return false;
    }
  }, true);
  var s = document.createElement('style');
  s.textContent = 'body{-webkit-user-select:none;user-select:none}input,textarea{-webkit-user-select:text;user-select:text}';
  (document.head || document.documentElement).appendChild(s);
})();
