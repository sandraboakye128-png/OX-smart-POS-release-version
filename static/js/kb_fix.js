
(function() {
    function updateVh() {
        var vh = window.visualViewport ? window.visualViewport.height : window.innerHeight;
        document.documentElement.style.setProperty('--vh', vh + 'px');
    }
    updateVh();
    if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', updateVh);
    } else {
        window.addEventListener('resize', updateVh);
    }
})();
