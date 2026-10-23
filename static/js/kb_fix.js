(function() {
    var baseHeight = window.innerHeight;
    
    function initKb() {
        if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Keyboard) {
            var Keyboard = window.Capacitor.Plugins.Keyboard;
            
            Keyboard.addListener('keyboardDidShow', function(info) {
                // Force the exact height (854 - 366 = 488)
                var newH = (baseHeight - info.keyboardHeight) + 'px';
                var app = document.querySelector('.app-container');
                if (app) app.style.height = newH;
                
                // Update the bug tracker
                var el = document.getElementById('bug-tracer');
                if (el) {
                    var div = document.createElement('div');
                    div.innerText = 'MANUAL RESIZE TO: ' + newH;
                    el.appendChild(div);
                }
            });
            
            Keyboard.addListener('keyboardDidHide', function() {
                var app = document.querySelector('.app-container');
                if (app) app.style.height = '100%';
            });
        }
    }
    
    document.addEventListener('deviceready', initKb, false);
    window.addEventListener('DOMContentLoaded', initKb);
})();
