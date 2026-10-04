# services/i18n.py
"""
Lightweight i18n for OX Smart POS.

- TRANSLATIONS dict: language_code -> { key: string }
- t(key, lang, **kwargs) — formats placeholders like {n}
- make_translator(user_id) — returns a closure bound to the user's language
- translations_for(lang) — merged dict for JS (window.OX_I18N)

Coverage notes (see TRANSLATIONS below):
  * Complete:   en, es, fr, pt, pcm
  * Good:       tw
  * Partial:    ha, yo, ig  (core nav + settings; missing keys → English)
  * Minimal:    ga, ewe      (labeled keys only; needs native review)

Adding a string:
  1. Add key to TRANSLATIONS['en']  (source of truth)
  2. Add translations under other languages — missing keys fall back to English
"""

from services.settings_service import get_language


DEFAULT_LANG = 'en'


# ============================================================
#  TRANSLATIONS
# ============================================================
TRANSLATIONS = {

    # ========================================================
    #  English — source of truth (must be complete)
    # ========================================================
    'en': {
        # Navigation
        'nav.dashboard':        'Dashboard',
        'nav.sales_acc':        'Sales (Accessories)',
        'nav.products_acc':     'Products (Accessories)',
        'nav.today_acc':        "Today's Sales (Accessories)",
        'nav.analytics':        'Analytics',
        'nav.archive':          'Archive',
        'nav.screens':          'Screens',
        'nav.sales_scr':        'Sales (Screens)',
        'nav.products_scr':     'Products (Screens)',
        'nav.today_scr':        "Today's Sales (Screens)",
        'nav.claims':           'Claims',
        'nav.logs':             'User Logs',
        'nav.purchases_acc':    'Purchases (Accessories)',
        'nav.purchases_scr':    'Purchases (Screens)',
        'nav.import':           'Import Data',
        'nav.users':            'Users',
        'nav.settings':         'Settings',
        'nav.offline':          'Open App in Offline Mode',
        'nav.logout':           'Logout',
        'nav.sync_offline':     'Sync Offline',
        'nav.clear_offline':    'Clear Offline Data',
        'nav.install_app':      'Install App',

        # Settings page — header
        'settings.title':       'Settings',
        'settings.subtitle':    'Customize your application preferences',
        'settings.save':        'Save Settings',
        'settings.saving':      'Saving…',
        'settings.save_ok':     '✅ Settings saved. Reloading…',
        'settings.save_fail':   '❌ Failed to save',

        # Live preview
        'settings.live_preview':'Live Preview',
        'settings.preview_sample': 'Sample text at your chosen font',
        'settings.preview_product': 'Product: Screen Protector (Tempered Glass)',
        'settings.preview_total': 'Total:',
        'settings.preview_date':  'Date preview:',
        'settings.preview_alert': '⚠️ Low stock alert when units ≤',

        # Theme
        'settings.section.theme':       'Theme',
        'settings.theme.light':         'Light',
        'settings.theme.light_desc':    'Default light theme',
        'settings.theme.dark':          'Dark',
        'settings.theme.dark_desc':     'Dark theme for night use',

        # Typography
        'settings.section.typography':       'Typography',
        'settings.font_size':                'Font Size',
        'settings.font_family':              'Font Family',
        'settings.font_size.small':          'Small (compact)',
        'settings.font_size.medium':         'Medium (default)',
        'settings.font_size.large':          'Large (easier to read)',
        'settings.font_size.xlarge':         'Extra Large (touch-friendly)',
        'settings.font_family.system':       'System Default (Sans-serif)',
        'settings.font_family.humanist':     'Humanist (Verdana / Tahoma)',
        'settings.font_family.serif':        'Serif (Georgia / Times)',
        'settings.font_family.mono':         'Monospace (Courier / Consolas)',
        'settings.font_family.rounded':      'Rounded (Comic / Trebuchet)',

        # Low stock
        'settings.section.low_stock':        'Low Stock Alerts',
        'settings.low_stock.explain':        'Products and batches at or below this quantity will be flagged as low stock on the dashboard, product pages, and alerts. Recommended: 2–5 for tight shops, 10 for larger inventory.',
        'settings.low_stock.threshold':      'Threshold (units)',
        'settings.low_stock.preset':         '{n} units',

        # Currency
        'settings.section.currency':         'Currency',
        'settings.currency_symbol':          'Currency Symbol',
        'settings.currency_code':            'Currency Code',

        # Language
        'settings.section.language':         'Language & Dates',
        'settings.language':                 'Interface Language',
        'settings.language.explain':         'Applies to the web app and offline shell. Some pages translate progressively.',
        'settings.date_format':              'Date Format',

        # Session info
        'settings.section.session':          'Session Info',
        'settings.session.user':             'User',
        'settings.session.role':             'Role',
        'settings.session.theme':            'Theme',
        'settings.session.threshold':        'Threshold',
    },

    # ========================================================
    #  Spanish — es
    # ========================================================
    'es': {
        'nav.dashboard':        'Panel',
        'nav.sales_acc':        'Ventas (Accesorios)',
        'nav.products_acc':     'Productos (Accesorios)',
        'nav.today_acc':        'Ventas de Hoy (Accesorios)',
        'nav.analytics':        'Analíticas',
        'nav.archive':          'Archivo',
        'nav.screens':          'Pantallas',
        'nav.sales_scr':        'Ventas (Pantallas)',
        'nav.products_scr':     'Productos (Pantallas)',
        'nav.today_scr':        'Ventas de Hoy (Pantallas)',
        'nav.claims':           'Reclamos',
        'nav.logs':             'Registros de Usuarios',
        'nav.purchases_acc':    'Compras (Accesorios)',
        'nav.purchases_scr':    'Compras (Pantallas)',
        'nav.import':           'Importar Datos',
        'nav.users':            'Usuarios',
        'nav.settings':         'Ajustes',
        'nav.offline':          'Abrir App en Modo Sin Conexión',
        'nav.logout':           'Cerrar Sesión',
        'nav.sync_offline':     'Sincronizar sin conexión',
        'nav.clear_offline':    'Borrar datos sin conexión',
        'nav.install_app':      'Instalar App',

        'settings.title':       'Ajustes',
        'settings.subtitle':    'Personaliza las preferencias de la aplicación',
        'settings.save':        'Guardar Ajustes',
        'settings.saving':      'Guardando…',
        'settings.save_ok':     '✅ Ajustes guardados. Recargando…',
        'settings.save_fail':   '❌ Error al guardar',
        'settings.live_preview':'Vista previa',
        'settings.preview_sample': 'Texto de muestra con tu fuente elegida',
        'settings.preview_product': 'Producto: Protector de pantalla (Vidrio templado)',
        'settings.preview_total': 'Total:',
        'settings.preview_date':  'Fecha:',
        'settings.preview_alert': '⚠️ Alerta de stock bajo cuando unidades ≤',

        'settings.section.theme':       'Tema',
        'settings.theme.light':         'Claro',
        'settings.theme.light_desc':    'Tema claro predeterminado',
        'settings.theme.dark':          'Oscuro',
        'settings.theme.dark_desc':     'Tema oscuro para uso nocturno',

        'settings.section.typography':       'Tipografía',
        'settings.font_size':                'Tamaño de fuente',
        'settings.font_family':              'Familia de fuente',
        'settings.font_size.small':          'Pequeño (compacto)',
        'settings.font_size.medium':         'Mediano (predeterminado)',
        'settings.font_size.large':          'Grande (más fácil de leer)',
        'settings.font_size.xlarge':         'Extra grande (táctil)',
        'settings.font_family.system':       'Predeterminada del sistema',
        'settings.font_family.humanist':     'Humanista (Verdana / Tahoma)',
        'settings.font_family.serif':        'Serif (Georgia / Times)',
        'settings.font_family.mono':         'Monoespaciada (Courier / Consolas)',
        'settings.font_family.rounded':      'Redondeada (Comic / Trebuchet)',

        'settings.section.low_stock':        'Alertas de stock bajo',
        'settings.low_stock.explain':        'Los productos y lotes en o por debajo de esta cantidad se marcarán como stock bajo en el panel, las páginas de productos y las alertas. Recomendado: 2–5 para tiendas pequeñas, 10 para inventario grande.',
        'settings.low_stock.threshold':      'Umbral (unidades)',
        'settings.low_stock.preset':         '{n} unidades',

        'settings.section.currency':         'Moneda',
        'settings.currency_symbol':          'Símbolo de moneda',
        'settings.currency_code':            'Código de moneda',

        'settings.section.language':         'Idioma y fechas',
        'settings.language':                 'Idioma de la interfaz',
        'settings.language.explain':         'Se aplica a la app web y al shell sin conexión. Algunas páginas se traducen progresivamente.',
        'settings.date_format':              'Formato de fecha',

        'settings.section.session':          'Sesión',
        'settings.session.user':             'Usuario',
        'settings.session.role':             'Rol',
        'settings.session.theme':            'Tema',
        'settings.session.threshold':        'Umbral',
    },

    # ========================================================
    #  French — fr
    # ========================================================
    'fr': {
        'nav.dashboard':        'Tableau de bord',
        'nav.sales_acc':        'Ventes (Accessoires)',
        'nav.products_acc':     'Produits (Accessoires)',
        'nav.today_acc':        "Ventes du jour (Accessoires)",
        'nav.analytics':        'Analytique',
        'nav.archive':          'Archives',
        'nav.screens':          'Écrans',
        'nav.sales_scr':        'Ventes (Écrans)',
        'nav.products_scr':     'Produits (Écrans)',
        'nav.today_scr':        "Ventes du jour (Écrans)",
        'nav.claims':           'Réclamations',
        'nav.logs':             'Journaux utilisateurs',
        'nav.purchases_acc':    'Achats (Accessoires)',
        'nav.purchases_scr':    'Achats (Écrans)',
        'nav.import':           'Importer des données',
        'nav.users':            'Utilisateurs',
        'nav.settings':         'Paramètres',
        'nav.offline':          "Ouvrir l'app en mode hors ligne",
        'nav.logout':           'Déconnexion',
        'nav.sync_offline':     'Synchroniser hors ligne',
        'nav.clear_offline':    'Effacer les données hors ligne',
        'nav.install_app':      "Installer l'app",

        'settings.title':       'Paramètres',
        'settings.subtitle':    "Personnalisez les préférences de l'application",
        'settings.save':        'Enregistrer',
        'settings.saving':      'Enregistrement…',
        'settings.save_ok':     '✅ Paramètres enregistrés. Rechargement…',
        'settings.save_fail':   "❌ Échec de l'enregistrement",
        'settings.live_preview':'Aperçu',
        'settings.preview_sample': 'Texte de démonstration avec votre police',
        'settings.preview_product': "Produit : Protecteur d'écran (verre trempé)",
        'settings.preview_total': 'Total :',
        'settings.preview_date':  'Date :',
        'settings.preview_alert': '⚠️ Alerte de stock faible quand unités ≤',

        'settings.section.theme':       'Thème',
        'settings.theme.light':         'Clair',
        'settings.theme.light_desc':    'Thème clair par défaut',
        'settings.theme.dark':          'Sombre',
        'settings.theme.dark_desc':     'Thème sombre pour la nuit',

        'settings.section.typography':       'Typographie',
        'settings.font_size':                'Taille de police',
        'settings.font_family':              'Famille de police',
        'settings.font_size.small':          'Petite (compacte)',
        'settings.font_size.medium':         'Moyenne (par défaut)',
        'settings.font_size.large':          'Grande (plus lisible)',
        'settings.font_size.xlarge':         'Très grande (tactile)',
        'settings.font_family.system':       'Par défaut du système',
        'settings.font_family.humanist':     'Humaniste (Verdana / Tahoma)',
        'settings.font_family.serif':        'Serif (Georgia / Times)',
        'settings.font_family.mono':         'Monospace (Courier / Consolas)',
        'settings.font_family.rounded':      'Arrondie (Comic / Trebuchet)',

        'settings.section.low_stock':        'Alertes stock faible',
        'settings.low_stock.explain':        'Les produits et lots à ou sous cette quantité seront signalés comme stock faible sur le tableau de bord, les pages produits et les alertes. Recommandé : 2–5 pour petites boutiques, 10 pour inventaires plus grands.',
        'settings.low_stock.threshold':      'Seuil (unités)',
        'settings.low_stock.preset':         '{n} unités',

        'settings.section.currency':         'Devise',
        'settings.currency_symbol':          'Symbole monétaire',
        'settings.currency_code':            'Code devise',

        'settings.section.language':         'Langue et dates',
        'settings.language':                 "Langue de l'interface",
        'settings.language.explain':         "S'applique à l'app web et au shell hors ligne. Certaines pages se traduisent progressivement.",
        'settings.date_format':              'Format de date',

        'settings.section.session':          'Session',
        'settings.session.user':             'Utilisateur',
        'settings.session.role':             'Rôle',
        'settings.session.theme':            'Thème',
        'settings.session.threshold':        'Seuil',
    },

    # ========================================================
    #  Portuguese — pt
    # ========================================================
    'pt': {
        'nav.dashboard':        'Painel',
        'nav.sales_acc':        'Vendas (Acessórios)',
        'nav.products_acc':     'Produtos (Acessórios)',
        'nav.today_acc':        'Vendas de Hoje (Acessórios)',
        'nav.analytics':        'Análises',
        'nav.archive':          'Arquivo',
        'nav.screens':          'Telas',
        'nav.sales_scr':        'Vendas (Telas)',
        'nav.products_scr':     'Produtos (Telas)',
        'nav.today_scr':        'Vendas de Hoje (Telas)',
        'nav.claims':           'Reclamações',
        'nav.logs':             'Logs de Usuários',
        'nav.purchases_acc':    'Compras (Acessórios)',
        'nav.purchases_scr':    'Compras (Telas)',
        'nav.import':           'Importar Dados',
        'nav.users':            'Usuários',
        'nav.settings':         'Configurações',
        'nav.offline':          'Abrir App em Modo Offline',
        'nav.logout':           'Sair',
        'nav.sync_offline':     'Sincronizar Offline',
        'nav.clear_offline':    'Limpar Dados Offline',
        'nav.install_app':      'Instalar App',

        'settings.title':       'Configurações',
        'settings.subtitle':    'Personalize as preferências do aplicativo',
        'settings.save':        'Salvar Configurações',
        'settings.saving':      'Salvando…',
        'settings.save_ok':     '✅ Configurações salvas. Recarregando…',
        'settings.save_fail':   '❌ Falha ao salvar',
        'settings.live_preview':'Pré-visualização',
        'settings.preview_sample': 'Texto de exemplo com sua fonte escolhida',
        'settings.preview_product': 'Produto: Protetor de Tela (Vidro Temperado)',
        'settings.preview_total': 'Total:',
        'settings.preview_date':  'Data:',
        'settings.preview_alert': '⚠️ Alerta de estoque baixo quando unidades ≤',

        'settings.section.theme':       'Tema',
        'settings.theme.light':         'Claro',
        'settings.theme.light_desc':    'Tema claro padrão',
        'settings.theme.dark':          'Escuro',
        'settings.theme.dark_desc':     'Tema escuro para uso noturno',

        'settings.section.typography':       'Tipografia',
        'settings.font_size':                'Tamanho da Fonte',
        'settings.font_family':              'Família da Fonte',
        'settings.font_size.small':          'Pequena (compacta)',
        'settings.font_size.medium':         'Média (padrão)',
        'settings.font_size.large':          'Grande (mais fácil de ler)',
        'settings.font_size.xlarge':         'Extra Grande (toque)',
        'settings.font_family.system':       'Padrão do Sistema',
        'settings.font_family.humanist':     'Humanista (Verdana / Tahoma)',
        'settings.font_family.serif':        'Serifada (Georgia / Times)',
        'settings.font_family.mono':         'Monoespaçada (Courier / Consolas)',
        'settings.font_family.rounded':      'Arredondada (Comic / Trebuchet)',

        'settings.section.low_stock':        'Alertas de Estoque Baixo',
        'settings.low_stock.explain':        'Produtos e lotes nesta quantidade ou abaixo serão sinalizados como estoque baixo no painel, páginas de produtos e alertas. Recomendado: 2–5 para lojas pequenas, 10 para inventário maior.',
        'settings.low_stock.threshold':      'Limite (unidades)',
        'settings.low_stock.preset':         '{n} unidades',

        'settings.section.currency':         'Moeda',
        'settings.currency_symbol':          'Símbolo da Moeda',
        'settings.currency_code':            'Código da Moeda',

        'settings.section.language':         'Idioma e Datas',
        'settings.language':                 'Idioma da Interface',
        'settings.language.explain':         'Aplica-se ao app web e shell offline. Algumas páginas são traduzidas progressivamente.',
        'settings.date_format':              'Formato de Data',

        'settings.section.session':          'Sessão',
        'settings.session.user':             'Usuário',
        'settings.session.role':             'Função',
        'settings.session.theme':            'Tema',
        'settings.session.threshold':        'Limite',
    },

    # ========================================================
    #  Nigerian Pidgin — pcm
    #  Close to English with local flavor; easy to keep complete.
    # ========================================================
    'pcm': {
        'nav.dashboard':        'Dashboard',
        'nav.sales_acc':        'Sales (Accessories)',
        'nav.products_acc':     'Products (Accessories)',
        'nav.today_acc':        'Today Sales (Accessories)',
        'nav.analytics':        'Analytics',
        'nav.archive':          'Store Old Things',
        'nav.screens':          'Screens',
        'nav.sales_scr':        'Sales (Screens)',
        'nav.products_scr':     'Products (Screens)',
        'nav.today_scr':        'Today Sales (Screens)',
        'nav.claims':           'Complaints',
        'nav.logs':             'User Activity',
        'nav.purchases_acc':    'Purchases (Accessories)',
        'nav.purchases_scr':    'Purchases (Screens)',
        'nav.import':           'Bring Data Enter',
        'nav.users':            'Users',
        'nav.settings':         'Settings',
        'nav.offline':          'Open App When Network No Dey',
        'nav.logout':           'Comot',
        'nav.sync_offline':     'Sync Offline',
        'nav.clear_offline':    'Clear Offline Data',
        'nav.install_app':      'Install App',

        'settings.title':       'Settings',
        'settings.subtitle':    'Change how your app dey work',
        'settings.save':        'Save Settings',
        'settings.saving':      'E dey save…',
        'settings.save_ok':     '✅ E don save. E dey reload…',
        'settings.save_fail':   '❌ E no save',
        'settings.live_preview':'See Am First',
        'settings.preview_sample': 'Sample text for the font wey you pick',
        'settings.preview_product': 'Product: Screen Protector (Tempered Glass)',
        'settings.preview_total': 'Total:',
        'settings.preview_date':  'Date:',
        'settings.preview_alert': '⚠️ Low stock warning when units ≤',

        'settings.section.theme':       'Theme',
        'settings.theme.light':         'Bright',
        'settings.theme.light_desc':    'Normal bright theme',
        'settings.theme.dark':          'Dark',
        'settings.theme.dark_desc':     'Dark theme for night',

        'settings.section.typography':       'Font Style',
        'settings.font_size':                'Font Size',
        'settings.font_family':              'Font Style',
        'settings.font_size.small':          'Small',
        'settings.font_size.medium':         'Normal',
        'settings.font_size.large':          'Big',
        'settings.font_size.xlarge':         'Very Big',
        'settings.font_family.system':       'System Default',
        'settings.font_family.humanist':     'Humanist',
        'settings.font_family.serif':        'Serif',
        'settings.font_family.mono':         'Mono',
        'settings.font_family.rounded':      'Rounded',

        'settings.section.low_stock':        'Low Stock Warning',
        'settings.low_stock.explain':        'Any product or batch wey reach this number go show as low stock for dashboard, products page and alert. Better pick 2–5 for small shop, 10 for big shop.',
        'settings.low_stock.threshold':      'Number (units)',
        'settings.low_stock.preset':         '{n} units',

        'settings.section.currency':         'Money',
        'settings.currency_symbol':          'Money Sign',
        'settings.currency_code':            'Money Code',

        'settings.section.language':         'Language & Dates',
        'settings.language':                 'Language for App',
        'settings.language.explain':         'E go change web app and offline shell. Some pages dey translate small small.',
        'settings.date_format':              'Date Format',

        'settings.section.session':          'Account Info',
        'settings.session.user':             'User',
        'settings.session.role':             'Role',
        'settings.session.theme':            'Theme',
        'settings.session.threshold':        'Number',
    },

    # ========================================================
    #  Twi — tw
    #  Best-effort; native review recommended.
    # ========================================================
    'tw': {
        'nav.dashboard':        'Dashboard',
        'nav.sales_acc':        'Nnɛdɛ (Accessories)',
        'nav.products_acc':     'Nneɛma (Accessories)',
        'nav.today_acc':        'Nnɛ Nnɛdɛ (Accessories)',
        'nav.analytics':        'Nhyehyɛe',
        'nav.archive':          'Korabea',
        'nav.screens':          'Screen',
        'nav.sales_scr':        'Nnɛdɛ (Screen)',
        'nav.products_scr':     'Nneɛma (Screen)',
        'nav.today_scr':        'Nnɛ Nnɛdɛ (Screen)',
        'nav.claims':           'Ntɛmpɛ',
        'nav.logs':             'Adwuma Nsɛm',
        'nav.purchases_acc':    'Nnɛdɛ (Accessories)',
        'nav.purchases_scr':    'Nnɛdɛ (Screen)',
        'nav.import':           'Fa Data Ba',
        'nav.users':            'Adwumafoɔ',
        'nav.settings':         'Nhyehyɛe',
        'nav.offline':          'Bue App no wɔ Offline Mode',
        'nav.logout':           'Fi Mu',
        'nav.sync_offline':     'Sync Offline',
        'nav.clear_offline':    'Popa Offline Data',
        'nav.install_app':      'Fa App no Gu',

        'settings.title':       'Nhyehyɛe',
        'settings.subtitle':    "Sesa w'app no sɛdeɛ ɛpɛ w'akoma",
        'settings.save':        'Sie Nhyehyɛe',
        'settings.saving':      'Ɛresie…',
        'settings.save_ok':     "✅ W'asie! Ɛre-san hyɛ aseɛ…",
        'settings.save_fail':   '❌ Antumi ansie',
        'settings.live_preview':'Nhunu Nsɛm',
        'settings.preview_sample': "Kyerɛw a ɛwɔ w'akyi",
        'settings.preview_product': 'Adwuma: Screen Protector',
        'settings.preview_total': 'Nyinaa:',
        'settings.preview_date':  'Da:',
        'settings.preview_alert': '⚠️ Nneɛma kakra alert berɛ units ≤',

        'settings.section.theme':       'Ahosɛpɛ',
        'settings.theme.light':         'Hann',
        'settings.theme.light_desc':    'Hann ahosɛpɛ',
        'settings.theme.dark':          'Sum',
        'settings.theme.dark_desc':     'Sum ahosɛpɛ anadwo',

        'settings.section.typography':       'Nkyerɛwee',
        'settings.font_size':                'Nkyerɛwee Kɛseɛ',
        'settings.font_family':              'Nkyerɛwee Su',
        'settings.font_size.small':          'Ketewa',
        'settings.font_size.medium':         'Mfinimfini',
        'settings.font_size.large':          'Kɛseɛ',
        'settings.font_size.xlarge':         'Kɛseɛ Paa',
        'settings.font_family.system':       'System Default',
        'settings.font_family.humanist':     'Humanist',
        'settings.font_family.serif':        'Serif',
        'settings.font_family.mono':         'Monospace',
        'settings.font_family.rounded':      'Rounded',

        'settings.section.low_stock':        'Nneɛma Kakra Alert',
        'settings.low_stock.explain':        'Nneɛma a ɛwɔ ha ara pɛ na ɛbɛyɛ kakra wɔ dashboard no so.',
        'settings.low_stock.threshold':      'Kakra Beaeɛ',
        'settings.low_stock.preset':         'Units {n}',

        'settings.section.currency':         'Sika',
        'settings.currency_symbol':          'Sika Symbol',
        'settings.currency_code':            'Sika Code',

        'settings.section.language':         'Kasa & Nna',
        'settings.language':                 'Kasa',
        'settings.language.explain':         'Ɛfa web app ne offline shell so.',
        'settings.date_format':              'Da Format',

        'settings.section.session':          'Berɛ',
        'settings.session.user':             'Onipa',
        'settings.session.role':             'Dwuma',
        'settings.session.theme':            'Ahosɛpɛ',
        'settings.session.threshold':        'Kakra Beaeɛ',
    },

    # ========================================================
    #  Hausa — ha
    #  Core terms only; native review recommended.
    # ========================================================
    'ha': {
        'nav.dashboard':        'Dashboard',
        'nav.sales_acc':        'Sayarwa (Kayan Aiki)',
        'nav.products_acc':     'Kayayyaki (Kayan Aiki)',
        'nav.today_acc':        'Sayarwar Yau (Kayan Aiki)',
        'nav.analytics':        'Nazari',
        'nav.archive':          'Rijiyar Tsofaffi',
        'nav.screens':          'Allon Wayoyi',
        'nav.sales_scr':        'Sayarwa (Allon Wayoyi)',
        'nav.products_scr':     'Kayayyaki (Allon Wayoyi)',
        'nav.today_scr':        'Sayarwar Yau (Allon Wayoyi)',
        'nav.claims':           'Korafe-korafe',
        'nav.logs':             'Ayyukan Masu Amfani',
        'nav.purchases_acc':    'Sayayya (Kayan Aiki)',
        'nav.purchases_scr':    'Sayayya (Allon Wayoyi)',
        'nav.import':           'Shigo da Bayanai',
        'nav.users':            'Masu Amfani',
        'nav.settings':         'Saituna',
        'nav.offline':          'Buɗe App cikin Yanayin Offline',
        'nav.logout':           'Fita',
        'nav.sync_offline':     'Daidaita Offline',
        'nav.clear_offline':    'Share Bayanan Offline',
        'nav.install_app':      'Shigar da App',

        'settings.title':       'Saituna',
        'settings.subtitle':    'Gyara yadda app ɗinka yake aiki',
        'settings.save':        'Ajiye Saituna',
        'settings.saving':      'Ana ajiyewa…',
        'settings.save_ok':     '✅ An ajiye. Ana sake buɗewa…',
        'settings.save_fail':   '❌ An kasa ajiyewa',
        'settings.live_preview':'Duba Kafin Ajiya',
        'settings.preview_sample': 'Misalin rubutu da font ɗinka',
        'settings.preview_product': 'Kaya: Screen Protector',
        'settings.preview_total': 'Jimilla:',
        'settings.preview_date':  'Kwanan wata:',
        'settings.preview_alert': '⚠️ Faɗakarwar ƙarancin kaya idan units ≤',

        'settings.section.theme':       'Jigo',
        'settings.theme.light':         'Haske',
        'settings.theme.light_desc':    'Jigo mai haske',
        'settings.theme.dark':          'Duhu',
        'settings.theme.dark_desc':     'Jigo mai duhu don dare',

        'settings.section.typography':       'Salon Rubutu',
        'settings.font_size':                'Girman Rubutu',
        'settings.font_family':              'Irin Rubutu',
        'settings.font_size.small':          'Ƙarami',
        'settings.font_size.medium':         'Matsakaici',
        'settings.font_size.large':          'Babba',
        'settings.font_size.xlarge':         'Babba Sosai',
        'settings.font_family.system':       'Na Asali',
        'settings.font_family.humanist':     'Humanist',
        'settings.font_family.serif':        'Serif',
        'settings.font_family.mono':         'Monospace',
        'settings.font_family.rounded':      'Rounded',

        'settings.section.low_stock':        'Faɗakarwar Ƙarancin Kaya',
        'settings.low_stock.explain':        'Duk wani kaya da ya kai wannan adadi za a nuna shi ƙarami a dashboard, shafukan kaya, da faɗakarwa. Shawara: 2–5 don ƙananan shaguna, 10 don babban ajiya.',
        'settings.low_stock.threshold':      'Iyaka (units)',
        'settings.low_stock.preset':         '{n} units',

        'settings.section.currency':         'Kuɗi',
        'settings.currency_symbol':          'Alamar Kuɗi',
        'settings.currency_code':            'Lambar Kuɗi',

        'settings.section.language':         'Harshe da Kwanaki',
        'settings.language':                 'Harshen App',
        'settings.language.explain':         'Ya shafi web app da offline shell.',
        'settings.date_format':              'Tsarin Kwanan Wata',

        'settings.section.session':          'Bayanan Zama',
        'settings.session.user':             'Mai Amfani',
        'settings.session.role':             'Matsayi',
        'settings.session.theme':            'Jigo',
        'settings.session.threshold':        'Iyaka',
    },

    # ========================================================
    #  Yoruba — yo
    #  Core terms only; native review recommended.
    # ========================================================
    'yo': {
        'nav.dashboard':        'Pátákó Ìṣàkóso',
        'nav.sales_acc':        'Títà (Àwọn Ẹ̀yà)',
        'nav.products_acc':     'Àwọn Ọjà (Àwọn Ẹ̀yà)',
        'nav.today_acc':        'Títà Òní (Àwọn Ẹ̀yà)',
        'nav.analytics':        'Ìtúpalẹ̀',
        'nav.archive':          'Ilé Ìkóra',
        'nav.screens':          'Àwọn Ojú-ìwé',
        'nav.sales_scr':        'Títà (Àwọn Ojú-ìwé)',
        'nav.products_scr':     'Àwọn Ọjà (Àwọn Ojú-ìwé)',
        'nav.today_scr':        'Títà Òní (Àwọn Ojú-ìwé)',
        'nav.claims':           'Àwọn Ẹ̀sùn',
        'nav.logs':             'Ìṣe Àwọn Olùmúlò',
        'nav.purchases_acc':    'Ìrajà (Àwọn Ẹ̀yà)',
        'nav.purchases_scr':    'Ìrajà (Àwọn Ojú-ìwé)',
        'nav.import':           'Gbin Dátà Wọlé',
        'nav.users':            'Àwọn Olùmúlò',
        'nav.settings':         'Ètò',
        'nav.offline':          'Ṣí App ní Offline Mode',
        'nav.logout':           'Jáde',
        'nav.sync_offline':     'Sopọ̀ Offline',
        'nav.clear_offline':    'Pa Dátà Offline',
        'nav.install_app':      'Fi App Sórí',

        'settings.title':       'Ètò',
        'settings.subtitle':    'Ṣàtúnṣe àwọn ìfẹ́ rẹ nípa app',
        'settings.save':        'Fi Ètò Sọ́nà',
        'settings.saving':      'Ń gbà…',
        'settings.save_ok':     '✅ Ó ti gbà. Ń tún ṣí…',
        'settings.save_fail':   '❌ Kò gbà',
        'settings.live_preview':'Wo Ṣáájú',
        'settings.preview_sample': 'Ọ̀rọ̀ àpẹẹrẹ pẹ̀lú font rẹ',
        'settings.preview_product': 'Ọjà: Screen Protector',
        'settings.preview_total': 'Àpapọ̀:',
        'settings.preview_date':  'Ọjọ́:',
        'settings.preview_alert': '⚠️ Ìkìlọ̀ ọjà tó kéré nígbà tí units ≤',

        'settings.section.theme':       'Àwọ̀',
        'settings.theme.light':         'Ìmọ́lẹ̀',
        'settings.theme.light_desc':    'Àwọ̀ ìmọ́lẹ̀',
        'settings.theme.dark':          'Òkùnkùn',
        'settings.theme.dark_desc':     'Àwọ̀ òkùnkùn fún alẹ́',

        'settings.section.typography':       'Ìrísí Ìkọ̀wé',
        'settings.font_size':                'Ìwọ̀n Ìkọ̀wé',
        'settings.font_family':              'Irú Ìkọ̀wé',
        'settings.font_size.small':          'Kékeré',
        'settings.font_size.medium':         'Àárín',
        'settings.font_size.large':          'Ńlá',
        'settings.font_size.xlarge':         'Ńlá Gan',
        'settings.font_family.system':       'Ìpilẹ̀ Ẹ̀rọ',
        'settings.font_family.humanist':     'Humanist',
        'settings.font_family.serif':        'Serif',
        'settings.font_family.mono':         'Monospace',
        'settings.font_family.rounded':      'Rounded',

        'settings.section.low_stock':        'Ìkìlọ̀ Ọjà Kékeré',
        'settings.low_stock.explain':        'Ọjà tàbí batch tó bá dé iye yìí ni yóò hàn gẹ́gẹ́ bí ọjà kékeré lórí dashboard, ojú-ìwé ọjà, àti àwọn ìkìlọ̀. Ìmọ̀ràn: 2–5 fún ṣọ́ọ̀bù kékeré, 10 fún ilé ìpamọ́ ńlá.',
        'settings.low_stock.threshold':      'Ìwọ̀n (units)',
        'settings.low_stock.preset':         'Units {n}',

        'settings.section.currency':         'Owó',
        'settings.currency_symbol':          'Àmì Owó',
        'settings.currency_code':            'Kóòdù Owó',

        'settings.section.language':         'Èdè àti Ọjọ́',
        'settings.language':                 'Èdè App',
        'settings.language.explain':         'Ó kan web app àti offline shell.',
        'settings.date_format':              'Ọ̀nà Ọjọ́',

        'settings.section.session':          'Ìsọfúnni Ìpàdé',
        'settings.session.user':             'Olùmúlò',
        'settings.session.role':             'Ipa',
        'settings.session.theme':            'Àwọ̀',
        'settings.session.threshold':        'Ìwọ̀n',
    },

    # ========================================================
    #  Igbo — ig
    #  Core terms only; native review recommended.
    # ========================================================
    'ig': {
        'nav.dashboard':        'Ebe Nchịkwa',
        'nav.sales_acc':        'Ahịa (Ngwa)',
        'nav.products_acc':     'Ngwaahịa (Ngwa)',
        'nav.today_acc':        'Ahịa Taa (Ngwa)',
        'nav.analytics':        'Nyocha',
        'nav.archive':          'Ebe Nchekwa',
        'nav.screens':          'Ihuenyo',
        'nav.sales_scr':        'Ahịa (Ihuenyo)',
        'nav.products_scr':     'Ngwaahịa (Ihuenyo)',
        'nav.today_scr':        'Ahịa Taa (Ihuenyo)',
        'nav.claims':           'Mkpesa',
        'nav.logs':             'Ọrụ Ndị Ọrụ',
        'nav.purchases_acc':    'Ịzụta (Ngwa)',
        'nav.purchases_scr':    'Ịzụta (Ihuenyo)',
        'nav.import':           'Bubata Data',
        'nav.users':            'Ndị Ọrụ',
        'nav.settings':         'Ntọala',
        'nav.offline':          'Mepee App na Offline Mode',
        'nav.logout':           'Pụọ',
        'nav.sync_offline':     'Mezie Offline',
        'nav.clear_offline':    'Hichapụ Data Offline',
        'nav.install_app':      'Wụnye App',

        'settings.title':       'Ntọala',
        'settings.subtitle':    'Hazie otu app gị si arụ ọrụ',
        'settings.save':        'Chekwaa Ntọala',
        'settings.saving':      'Na-echekwa…',
        'settings.save_ok':     '✅ Echekwara. Na-emegharị…',
        'settings.save_fail':   '❌ Emechaghị',
        'settings.live_preview':'Lelee Tupu Chekwaa',
        'settings.preview_sample': 'Ihe atụ nke font ị họọrọ',
        'settings.preview_product': 'Ngwaahịa: Screen Protector',
        'settings.preview_total': 'Mkpokọta:',
        'settings.preview_date':  'Ụbọchị:',
        'settings.preview_alert': '⚠️ Ịdọ aka ná ntị ngwaahịa dị ntakịrị mgbe units ≤',

        'settings.section.theme':       'Isiokwu',
        'settings.theme.light':         'Ìhè',
        'settings.theme.light_desc':    'Isiokwu ìhè',
        'settings.theme.dark':          'Ọchịchịrị',
        'settings.theme.dark_desc':     'Isiokwu ọchịchịrị maka abalị',

        'settings.section.typography':       'Ụdị Edemede',
        'settings.font_size':                'Nha Edemede',
        'settings.font_family':              'Ụdị Edemede',
        'settings.font_size.small':          'Nta',
        'settings.font_size.medium':         'Etiti',
        'settings.font_size.large':          'Nnukwu',
        'settings.font_size.xlarge':         'Nnukwu Nke Ukwuu',
        'settings.font_family.system':       'Nke Sistemụ',
        'settings.font_family.humanist':     'Humanist',
        'settings.font_family.serif':        'Serif',
        'settings.font_family.mono':         'Monospace',
        'settings.font_family.rounded':      'Rounded',

        'settings.section.low_stock':        'Ịdọ aka ná ntị Ngwaahịa Dị Nta',
        'settings.low_stock.explain':        'Ngwaahịa ma ọ bụ batch nke ruru ọnụọgụ a ga-egosi dịka ngwaahịa dị nta na dashboard, peeji ngwaahịa, na ọkwa. Ndụmọdụ: 2–5 maka obere ụlọ ahịa, 10 maka nnukwu.',
        'settings.low_stock.threshold':      'Oke (units)',
        'settings.low_stock.preset':         'Units {n}',

        'settings.section.currency':         'Ego',
        'settings.currency_symbol':          'Akara Ego',
        'settings.currency_code':            'Koodu Ego',

        'settings.section.language':         'Asụsụ na Ụbọchị',
        'settings.language':                 'Asụsụ App',
        'settings.language.explain':         'Ọ metụtara web app na offline shell.',
        'settings.date_format':              'Ụdị Ụbọchị',

        'settings.section.session':          'Ozi Nnọkọ',
        'settings.session.user':             'Onye Ọrụ',
        'settings.session.role':             'Ọrụ',
        'settings.session.theme':            'Isiokwu',
        'settings.session.threshold':        'Oke',
    },

    # ========================================================
    #  Ga — ga  (Ghana)
    #  NEEDS NATIVE REVIEW. Only the most common terms are
    #  attempted; everything else falls back to English.
    # ========================================================
    'ga': {
        'nav.dashboard':        'Dashboard',
        'nav.sales_acc':        'Jáámɔ (Accessories)',
        'nav.products_acc':     'Niiamɔ (Accessories)',
        'nav.today_acc':        'Ŋmɛnɛ Jáámɔ (Accessories)',
        'nav.screens':          'Screen',
        'nav.settings':         'Sane',
        'nav.logout':           'Je Kpo',
        'nav.users':            'Mɛi',
        'nav.claims':           'Sane Niatsɔɔlɔi',

        'settings.title':       'Sane',
        'settings.save':        'To Sane',
        'settings.saving':      'Etoɔ sane…',
        'settings.save_ok':     '✅ Ato sane. Eehe shi…',
        'settings.save_fail':   '❌ Atooo sane',
        'settings.section.theme':       'Hela',
        'settings.theme.light':         'Kɔɔ',
        'settings.theme.dark':          'Dzu',

        'settings.section.typography':       'Ŋmaaŋ',
        'settings.font_size':                'Ŋmaaŋ Kwɔɔ',
        'settings.font_family':              'Ŋmaaŋ Su',
        'settings.font_size.small':          'Kɛ',
        'settings.font_size.medium':         'Teŋ',
        'settings.font_size.large':          'Da',

        'settings.section.low_stock':        'Niiamɔ Kɛ Kɛ Kɛ',
        'settings.section.currency':         'Shika',
        'settings.currency_symbol':          'Shika Ami',
        'settings.section.language':         'Wiemɔ',
        'settings.language':                 'Wiemɔ',
        'settings.section.session':          'Gbɛi',
        'settings.session.user':             'Mɔ',
        'settings.session.role':             'Nitsumɔ',
    },

    # ========================================================
    #  Ewe — ewe  (Ghana/Togo)
    #  NEEDS NATIVE REVIEW. Only the most common terms are
    #  attempted; everything else falls back to English.
    # ========================================================
    'ewe': {
        'nav.dashboard':        'Dashboard',
        'nav.sales_acc':        'Asitsaɖi (Accessories)',
        'nav.products_acc':     'Nuwo (Accessories)',
        'nav.today_acc':        'Egbe Asitsaɖi (Accessories)',
        'nav.screens':          'Screen',
        'nav.settings':         'Ðoɖowɔɖi',
        'nav.logout':           'Do Go',
        'nav.users':            'Amewo',
        'nav.claims':           'Nyatakakawo',

        'settings.title':       'Ðoɖowɔɖi',
        'settings.save':        'Dzra Ðoɖowɔɖi',
        'settings.saving':      'Ele edzram…',
        'settings.save_ok':     '✅ Woedzra. Ele etrɔm…',
        'settings.save_fail':   '❌ Medzra o',
        'settings.section.theme':       'Dzedzeme',
        'settings.theme.light':         'Kekeli',
        'settings.theme.dark':          'Viviti',

        'settings.section.typography':       'Nuŋɔŋlɔ',
        'settings.font_size':                'Nuŋɔŋlɔ Lɔnlɔ',
        'settings.font_family':              'Nuŋɔŋlɔ Ƒome',
        'settings.font_size.small':          'Sue',
        'settings.font_size.medium':         'Titina',
        'settings.font_size.large':          'Gã',

        'settings.section.low_stock':        'Nu Sue Ɖoɖoɖo',
        'settings.section.currency':         'Ga',
        'settings.currency_symbol':          'Ga Dzesi',
        'settings.section.language':         'Gbe',
        'settings.language':                 'Gbe',
        'settings.section.session':          'Ɖoɖoɖo Ðe Ðo',
        'settings.session.user':             'Ame',
        'settings.session.role':             'Dɔwɔna',
    },
}


# ============================================================
#  Public API
# ============================================================
def available_languages():
    """Language codes we have any translations for."""
    return sorted(TRANSLATIONS.keys())


def _lookup(key, lang):
    """Return the raw string for (key, lang), falling back gracefully."""
    lang = (lang or DEFAULT_LANG).lower()
    tables = [TRANSLATIONS.get(lang, {}), TRANSLATIONS[DEFAULT_LANG]]
    for table in tables:
        if key in table:
            return table[key]
    return key  # last resort — returns the key so missing entries are obvious


def t(key, lang=DEFAULT_LANG, **kwargs):
    """
    Translate a key to the given language.

    t('nav.dashboard', 'es')                     -> 'Panel'
    t('settings.low_stock.preset', 'es', n=3)    -> '3 unidades'
    """
    raw = _lookup(key, lang)
    if not kwargs:
        return raw
    try:
        return raw.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return raw


def t_for_user(key, user_id, **kwargs):
    """Convenience helper: resolve the language from user settings, then t()."""
    try:
        lang = get_language(user_id)
    except Exception:
        lang = DEFAULT_LANG
    return t(key, lang, **kwargs)


def make_translator(user_id):
    """
    Return a closure bound to a user's language.

    Used by the Jinja context processor so templates can call
    {{ t('nav.dashboard') }} without passing the language every time.
    """
    try:
        lang = get_language(user_id)
    except Exception:
        lang = DEFAULT_LANG
    def _t(key, **kwargs):
        return t(key, lang, **kwargs)
    return _t


def translations_for(lang):
    """
    Full dict for a language, merged on top of English so the client
    has every key it might need. Used to expose window.OX_I18N.
    """
    lang = (lang or DEFAULT_LANG).lower()
    merged = dict(TRANSLATIONS[DEFAULT_LANG])
    merged.update(TRANSLATIONS.get(lang, {}))
    return merged