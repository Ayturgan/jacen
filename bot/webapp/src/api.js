const tg = window.Telegram?.WebApp;

export function safeTGAction(action) {
    if (tg) {
        try {
            action(tg);
        } catch (e) {
            console.error('TG API Error:', e);
        }
    }
}

export async function safeFetch(url, options = {}, successMsg = '') {
    try {
        const res = await fetch(url, options);
        let data = null;
        if (res.headers.get("content-type")?.includes("application/json")) {
            data = await res.json();
        }
        
        if (res.ok) {
            if(successMsg) safeTGAction(t => t.HapticFeedback.notificationOccurred('success'));
            return { success: true, data };
        } else {
            safeTGAction(t => t.showAlert(`Ошибка сервера: ${res.status}`));
            return { success: false, error: `Status ${res.status}` };
        }
    } catch (e) {
        safeTGAction(t => t.showAlert("Паутина порвана. Ошибка связи с сервером."));
        return { success: false, error: e };
    }
}
