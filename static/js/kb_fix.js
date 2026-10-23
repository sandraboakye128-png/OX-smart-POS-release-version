/* FINAL_KB_FIX_V53 -- no resize listeners, cannot loop, cannot steal focus */
(function () {
    'use strict';
    var activeEl = null;
    function applyKbHeight() {
        if (!window.visualViewport) return;
        var h = window.visualViewport.height + 'px';
        document.documentElement.style.height = h;
        if (document.body) document.body.style.height = h;
        var e = document.querySelector('.app-container');
        if (e) e.style.height = h;
        var w = document.querySelector('.main-content-wrapper');
        if (w) w.style.height = h;
    }
    function clearKbHeight() {
        document.documentElement.style.height = '';
        if (document.body) document.body.style.height = '';
        var e = document.querySelector('.app-container');
        if (e) e.style.height = '';
        var w = document.querySelector('.main-content-wrapper');
        if (w) w.style.height = '';
    }
    document.addEventListener('focusin', function (e) {
        var t = e.target;
        if (!t || (t.tagName !== 'INPUT' && t.tagName !== 'TEXTAREA' && t.tagName !== 'SELECT')) return;
        activeEl = t;
        setTimeout(applyKbHeight, 350);
    });
    document.addEventListener('focusout', function (e) {
        if (e.target !== activeEl) return;
        activeEl = null;
        setTimeout(function () {
            var x = document.activeElement;
            if (x && (x.tagName === 'INPUT' || x.tagName === 'TEXTAREA' || x.tagName === 'SELECT')) return;
            clearKbHeight();
        }, 150);
    });
})();
