/* FINAL_KB_FIX_V54 -- Handles both Web (visualViewport) and APK (Capacitor) */
(function () {
    'use strict';
    var activeEl = null;

    function applyHeight(h) {
        document.documentElement.style.height = h;
        if (document.body) document.body.style.height = h;
        var e = document.querySelector('.app-container');
        if (e) e.style.height = h;
        var w = document.querySelector('.main-content-wrapper');
        if (w) w.style.height = h;
    }

    function resetHeight() {
        document.documentElement.style.height = '';
        if (document.body) document.body.style.height = '';
        var e = document.querySelector('.app-container');
        if (e) e.style.height = '';
        var w = document.querySelector('.main-content-wrapper');
        if (w) w.style.height = '';
    }

    // 1. WEB FIX (Chrome/Safari)
    document.addEventListener('focusin', function (e) {
        var t = e.target;
        if (!t || (t.tagName !== 'INPUT' && t.tagName !== 'TEXTAREA' && t.tagName !== 'SELECT')) return;
        activeEl = t;
        setTimeout(function() {
            if (window.visualViewport) {
                applyHeight(window.visualViewport.height + 'px');
            }
        }, 350);
    });

    document.addEventListener('focusout', function (e) {
        if (e.target !== activeEl) return;
        activeEl = null;
        setTimeout(function () {
            var x = document.activeElement;
            if (x && (x.tagName === 'INPUT' || x.tagName === 'TEXTAREA' || x.tagName === 'SELECT')) return;
            resetHeight();
        }, 150);
    });

    // 2. APK FIX (Capacitor Native WebView)
    function setupCapacitor() {
        if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Keyboard) {
            var Keyboard = window.Capacitor.Plugins.Keyboard;
            
            Keyboard.addListener('keyboardDidShow', function (info) {
                // info.keyboardHeight gives exact px
                var h = (window.innerHeight - info.keyboardHeight) + 'px';
                applyHeight(h);
            });
            
            Keyboard.addListener('keyboardDidHide', function () {
                resetHeight();
            });
            console.log('Capacitor Keyboard API wired up!');
        } else {
            // Retry in case plugin loads late
            setTimeout(setupCapacitor, 500);
        }
    }
    
    if (window.Capacitor) {
        setupCapacitor();
    } else {
        document.addEventListener('deviceready', setupCapacitor, false);
    }
})();
