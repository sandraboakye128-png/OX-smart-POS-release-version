
/* MIC_EMBED_V8 - Perfectly embeds mic icon inside input wrappers */
(function() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    let activeRec = null;

    function attachMic(input) {
        // Skip login/signup and excel preview
        if (window.location.pathname.includes('login') || window.location.pathname.includes('signup')) return;
        if (input.closest('#pvStep3') || input.closest('.pv-sheet-fullscreen')) return;
        
        // Skip hidden, checkboxes, etc.
        if (input.dataset.hasMic || ['hidden','checkbox','radio','date','datetime-local'].includes(input.type) || input.readOnly) return;
        if (input.offsetParent === null) return;

        input.dataset.hasMic = 'true';

        // Create the icon
        const btn = document.createElement('button');
        btn.innerHTML = '🎤';
        btn.type = 'button';
        btn.style.cssText = 'position:absolute; right:6px; top:50%; transform:translateY(-50%); background:#10b981; color:#fff; border:none; border-radius:4px; padding:4px 8px; cursor:pointer; z-index:10; font-size:14px; display:flex; align-items:center; justify-content:center;';
        
        // Wrap the input in a relative container so the icon anchors to the input, not the whole page
        let parent = input.parentNode;
        if (getComputedStyle(parent).position !== 'relative' && !parent.classList.contains('pv-input-wrap')) {
            const wrap = document.createElement('div');
            wrap.className = 'pv-input-wrap';
            wrap.style.cssText = 'position:relative; width:100%; display:flex; align-items:center;';
            parent.insertBefore(wrap, input);
            wrap.appendChild(input);
            parent = wrap;
        } else {
            parent.style.position = 'relative';
        }

        parent.appendChild(btn);
        
        // Add padding to input so text doesn't hide behind the icon
        input.style.paddingRight = '40px';

        btn.addEventListener('click', (e) => {
            e.preventDefault();
            if (activeRec) { activeRec.stop(); return; }

            const rec = new SpeechRecognition();
            rec.lang = 'en-US';
            rec.interimResults = false;
            activeRec = rec;
            btn.style.background = '#ef4444'; // Red when recording

            rec.onresult = (event) => {
                let text = event.results[0][0].transcript;
                
                // Parse numbers (e.g. "fifty" -> "50")
                if (input.type === 'number' || (input.name && (input.name.includes('discount') || input.name.includes('quantity') || input.name.includes('price')))) {
                    const numMatch = text.match(/\d+(\.\d+)?/);
                    if (numMatch) text = numMatch[0];
                    else {
                        const words = {'fifty':'50', 'twenty':'20', 'ten':'10', 'five':'5', 'one hundred':'100'};
                        text = words[text.toLowerCase()] || text;
                    }
                }
                
                // Parse batch (e.g. "batch 4" -> "4")
                if (input.placeholder && input.placeholder.toLowerCase().includes('batch')) {
                    text = text.replace(/batch/gi, '').trim();
                }

                input.value = text;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            };

            rec.onerror = () => { btn.style.background = '#10b981'; activeRec = null; };
            rec.onend = () => { btn.style.background = '#10b981'; activeRec = null; };
            rec.start();
        });
    }

    function scan() {
        document.querySelectorAll('input[type="text"], input[type="search"], input[type="number"], input[type="email"], input:not([type])').forEach(attachMic);
    }

    setTimeout(scan, 1000);
    const obs = new MutationObserver(() => setTimeout(scan, 200));
    obs.observe(document.body, { childList: true, subtree: true });
})();
