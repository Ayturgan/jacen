import { useEffect, useState } from 'react';
import { safeFetch, safeTGAction } from '../api';

const VIEW_TABS = [
    { id: 'overview', label: 'Обзор', icon: '🜂' },
    { id: 'scene', label: 'Сцена', icon: '🎭' },
    { id: 'players', label: 'Игроки', icon: '🛡️' },
    { id: 'backstage', label: 'Сервис', icon: '⚙️' },
];

const SCENE_PHASE_LABELS = {
    setup: 'Завязка',
    exploration: 'Исследование',
    complication: 'Осложнение',
    conflict: 'Конфликт',
    aftermath: 'Последствия',
    transition: 'Переход',
};

const TENSION_LABELS = {
    low: 'Низкое',
    medium: 'Среднее',
    high: 'Высокое',
    critical: 'Критическое',
};

const FOCUS_LABELS = {
    roleplay: 'Ролевая сцена',
    discovery: 'Раскрытие',
    danger: 'Опасность',
    choice: 'Выбор',
    consequence: 'Последствия',
};

export default function AdminPanel({ data, onRefresh }) {
    const ws = data.world_state || {};
    const [activeView, setActiveView] = useState('overview');
    const [whisperChar, setWhisperChar] = useState(data.characters?.[0]?.id || '');
    const [whisperText, setWhisperText] = useState('');
    const [model, setModel] = useState(ws.gemini_model || 'gemini-2.5-flash');
    const [llmTier, setLlmTier] = useState(ws.llm_tier || 'free');
    const [botMode, setBotMode] = useState(ws.bot_mode || 'normal');
    const [gmActionMode, setGmActionMode] = useState(ws.gm_action_mode || 'auto');
    const [spotlight, setSpotlight] = useState(ws.active_spotlight || 'ALL');
    const [maxTurns, setMaxTurns] = useState(ws.spotlight_max_turns || '3');
    const [availableModels, setAvailableModels] = useState([]);

    const keyEvents = data.key_events || [];

    const worldSummary = {
        phase: SCENE_PHASE_LABELS[ws.scene_phase] || ws.scene_phase || 'Не задана',
        tension: TENSION_LABELS[ws.director_tension] || ws.director_tension || 'Низкое',
        focus: FOCUS_LABELS[ws.director_focus] || ws.director_focus || 'Ролевая сцена',
        pressure: parseInt(ws.pressure_clock || '0', 10) || 0,
        worldTurns: parseInt(ws.world_turn_counter || '0', 10) || 0,
    };
    const isQuestStarted = ws.quest_started === '1';
    const isQuestPaused = ws.quest_paused === '1';
    const questStatusLabel = !isQuestStarted ? 'Не начат' : isQuestPaused ? 'На паузе' : 'Идёт';
    const questStatusHint = isQuestPaused ? (ws.quest_pause_reason || 'Ожидает продолжения') : (ws.current_scene || 'Сцена ещё не задана');

    useEffect(() => {
        fetch('/api/available_models')
            .then(r => r.json())
            .then(d => setAvailableModels(d.models || []))
            .catch(() => {});
    }, []);

    useEffect(() => {
        setModel(ws.gemini_model || 'gemini-2.5-flash');
        setLlmTier(ws.llm_tier || 'free');
    }, [ws.gemini_model, ws.llm_tier]);

    const updateWorldKey = async (key, value, successMessage) => {
        const res = await safeFetch('/api/update_world', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, value }),
        }, true);
        if (res.success && successMessage) {
            safeTGAction(t => t.showAlert(successMessage));
        }
        return res.success;
    };

    const toggleBotMode = async (mode) => {
        setBotMode(mode);
        const ok = await updateWorldKey('bot_mode', mode, `Режим изменен: ${mode === 'normal' ? 'Обычный' : 'Гейм Мастер'}`);
        if (!ok) setBotMode(ws.bot_mode || 'normal');
    };

    const toggleGmActionMode = async (mode) => {
        setGmActionMode(mode);
        const ok = await updateWorldKey('gm_action_mode', mode, `Режим действий ГМа: ${mode === 'auto' ? 'Авто' : 'Проверка'}`);
        if (!ok) setGmActionMode(ws.gm_action_mode || 'auto');
    };

    const switchSpotlight = async (charId) => {
        setSpotlight(charId);
        const res = await safeFetch('/api/spotlight', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ char_id: charId }),
        }, true);
        if (res.success) safeTGAction(t => t.HapticFeedback.impactOccurred('medium'));
    };

    const updateMaxTurns = async (val) => {
        setMaxTurns(val);
        await safeFetch('/api/spotlight_settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ max_turns: parseInt(val, 10) || 1 }),
        });
    };

    const pauseQuest = async () => {
        const res = await safeFetch('/api/pause_quest', { method: 'POST' }, true);
        if (res.success) {
            safeTGAction(t => t.showAlert('Квест поставлен на паузу.'));
            onRefresh?.();
        }
    };

    const resumeQuest = async () => {
        const res = await safeFetch('/api/resume_quest', { method: 'POST' }, true);
        if (res.success) {
            safeTGAction(t => t.showAlert('Квест продолжен.'));
            onRefresh?.();
        }
    };

    const sendWhisper = async () => {
        if (!whisperText || !whisperChar) return;
        const res = await safeFetch('/api/whisper', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ char_id: whisperChar, text: whisperText }),
        }, true);
        if (res.success) {
            setWhisperText('');
            safeTGAction(t => t.showAlert('Видение отправлено.'));
        }
    };

    const updateModel = async (modelId) => {
        setModel(modelId);
        const res = await safeFetch('/api/update_model', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelId }),
        }, true);
        if (res.success && res.data?.status === 'ok') {
            safeTGAction(t => t.showAlert('Разум обновлен.'));
            return;
        }
        setModel(ws.gemini_model || 'gemini-2.5-flash');
        if (res.data?.message) safeTGAction(t => t.showAlert(res.data.message));
    };

    const updateLlmTier = async (tier) => {
        setLlmTier(tier);
        const res = await safeFetch('/api/update_llm_tier', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tier }),
        }, true);
        if (res.success && res.data?.status === 'ok') {
            if (res.data?.model) setModel(res.data.model);
            safeTGAction(t => t.showAlert(tier === 'paid' ? 'Paid-режим: только Gemini.' : 'Free-режим активирован.'));
            onRefresh?.();
        } else {
            setLlmTier(ws.llm_tier || 'free');
            if (res.data?.message) safeTGAction(t => t.showAlert(res.data.message));
        }
    };

    const resetGame = () => {
        safeTGAction(t => t.showConfirm('ЭТО НЕОБРАТИМО. Уничтожить текущий мир?', async (confirm) => {
            if (confirm) {
                const res = await safeFetch('/api/stop_quest', { method: 'POST' });
                if (res.success) {
                    safeTGAction(t2 => t2.showAlert('Мир пересобран из пепла.'));
                    onRefresh?.();
                    setTimeout(() => window.location.reload(), 1800);
                }
            }
        }));
    };

    const renderOverview = () => (
        <div className="admin-dashboard-grid">
            <SectionCard title="Сессия" subtitle="То, что ГМ должен видеть первым" tone="mystic">
                <div className="admin-metric-grid">
                    <MetricCard label="Режим" value={botMode === 'normal' ? 'Обычный' : 'Игровой'} hint={botMode === 'normal' ? 'Якен общается как персонаж' : 'Автономный Гейм Мастер'} />
                    <MetricCard label="Статус квеста" value={questStatusLabel} hint={questStatusHint} />
                    <MetricCard label="Сцена" value={ws.current_scene || 'Не задана'} hint={`Акт ${ws.current_act || '1'} · ${ws.current_location || 'Локация скрыта'}`} />
                    <MetricCard label="Фаза" value={worldSummary.phase} hint={`Фокус: ${worldSummary.focus}`} />
                    <MetricCard label="Spotlight" value={spotlight === 'ALL' ? 'Все герои' : spotlight} hint={`Автосмена через ${maxTurns} ход(а)`} />
                    <MetricCard label="Мозг" value={llmTier === 'paid' ? 'Paid' : 'Free'} hint={model || 'Модель не выбрана'} />
                </div>
                <div className="admin-segment-row">
                    <ModePill active={botMode === 'normal'} onClick={() => toggleBotMode('normal')} icon="👤" title="Обычный" subtitle="Скрыть механику кампании" />
                    <ModePill active={botMode === 'quest'} onClick={() => toggleBotMode('quest')} icon="🔮" title="Игровой" subtitle="Бот ведёт сессию как ГМ" />
                </div>
                <div className="admin-segment-row" style={{ marginTop: '12px' }}>
                    <ModePill active={llmTier === 'free'} onClick={() => updateLlmTier('free')} icon="🧩" title="Brain Free" subtitle="Базовый ключ и лимиты" compact />
                    <ModePill active={llmTier === 'paid'} onClick={() => updateLlmTier('paid')} icon="💎" title="Brain Paid" subtitle="Отдельный Gemini ключ" compact />
                </div>
                {botMode === 'quest' && (
                    <div className="admin-segment-row" style={{ marginTop: '12px' }}>
                        <ModePill active={gmActionMode === 'auto'} onClick={() => toggleGmActionMode('auto')} icon="⚡" title="Авто" subtitle="Бот сам разрешает действия" compact />
                        <ModePill active={gmActionMode === 'review'} onClick={() => toggleGmActionMode('review')} icon="👁" title="Проверка" subtitle="Ключевые действия идут на подтверждение" compact />
                    </div>
                )}
            </SectionCard>

            <SectionCard title="Режиссура" subtitle="Что бот собирается делать дальше" tone="gold">
                <div className="admin-metric-grid">
                    <MetricCard label="Напряжение" value={worldSummary.tension} hint={ws.pressure_event || 'Мир ещё выжидает'} />
                    <MetricCard label="Давление" value={`${worldSummary.pressure}`} hint={ws.director_last_beat || 'Бит ещё не записан'} />
                    <MetricCard label="Ходов мира" value={`${worldSummary.worldTurns}`} hint={ws.last_world_event || 'Мир ещё не сделал явный ход'} />
                    <MetricCard label="Вопрос сцены" value={ws.dramatic_question || 'Не определён'} hint={ws.scene_goal || 'Цель сцены не задана'} wide />
                </div>
            </SectionCard>

            <SectionCard title="Ключевые изменения" subtitle="Смены имени, статусов и предметов" tone="gold">
                <div className="admin-timeline">
                    {keyEvents.length > 0 ? keyEvents.map((event, idx) => (
                        <div key={idx} className="admin-timeline-item">
                            <b>[{event.event_type || 'event'}]</b> {event.description}
                            {event.timestamp && <small style={{ color: '#888', marginLeft: '8px' }}>{event.timestamp}</small>}
                        </div>
                    )) : <div className="admin-empty-state">Ключевых изменений пока нет.</div>}
                </div>
            </SectionCard>

            <SectionCard title="Быстрые GM-ходы" subtitle="Минимум ручного управления" tone="danger">
                <div className="admin-action-grid">
                    <QuickActionButton title={isQuestPaused ? 'Продолжить квест' : 'Пауза квеста'} hint={isQuestPaused ? 'Вернуть сохранённую сцену' : 'Заморозить сцену до следующего дня'} onClick={isQuestPaused ? resumeQuest : pauseQuest} />
                    <QuickActionButton title="Все в кадре" hint="Вернуть общий фокус" onClick={() => switchSpotlight('ALL')} />
                    <QuickActionButton title="Шёпот игроку" hint="Тайное видение или подсказка" onClick={() => setActiveView('scene')} />
                </div>
                <div className="admin-note-box">
                    <div className="admin-note-title">Совет</div>
                    <p>Сцены и акты теперь двигает сам ГМ-ИИ. Админка оставляет только наблюдение, паузу/продолжение и точечные служебные действия.</p>
                </div>
            </SectionCard>
        </div>
    );

    const renderScene = () => (
        <div className="admin-dashboard-grid admin-dashboard-grid--two">
            <SectionCard title="Текущая сцена" subtitle="AI-режиссура в реальном времени">
                <div className="admin-metric-grid" style={{ marginBottom: '12px' }}>
                    <MetricCard label="Акт" value={`Акт ${ws.current_act || '1'}`} hint={ws.current_location || 'Локация не задана'} />
                    <MetricCard label="Сцена" value={ws.current_scene || 'Не задана'} hint={ws.scene_goal || 'Цель сцены не задана'} wide />
                </div>
                <div className="admin-note-box" style={{ marginTop: '14px' }}>
                    <div className="admin-note-title">Автономный ГМ сейчас</div>
                    <p><b>Цель:</b> {ws.scene_goal || 'Бот сам определяет цель на основании текущего акта.'}</p>
                    <p><b>Фаза:</b> {worldSummary.phase}</p>
                    <p><b>Надвигается:</b> {ws.pressure_event || 'Пока ничего явного.'}</p>
                    {isQuestPaused && <p><b>Пауза:</b> {ws.quest_pause_reason || 'Сцена сохранена до продолжения.'}</p>}
                </div>
                <div className="admin-action-grid" style={{ marginTop: '14px' }}>
                    <button className="btn-action" onClick={isQuestPaused ? resumeQuest : pauseQuest}>{isQuestPaused ? '▶️ Продолжить' : '⏸ Пауза'}</button>
                </div>
            </SectionCard>

            <SectionCard title="Камера и шёпоты" subtitle="Единственные ручные действия, которые чаще всего нужны">
                <span className="stat-label">Фокус камеры</span>
                <div className="admin-chip-grid">
                    <ChoiceChip active={spotlight === 'ALL'} onClick={() => switchSpotlight('ALL')}>👥 Все</ChoiceChip>
                    {data.characters.map(char => (
                        <ChoiceChip key={char.id} active={spotlight === char.id} onClick={() => switchSpotlight(char.id)}>{char.name}</ChoiceChip>
                    ))}
                </div>
                <div className="admin-inline-field">
                    <span className="stat-label" style={{ margin: 0 }}>Автосмена</span>
                    <input type="number" value={maxTurns} onChange={e => updateMaxTurns(e.target.value)} min="1" max="10" style={{ width: '80px', textAlign: 'center' }} />
                </div>

                <span className="stat-label">Тайный шёпот</span>
                <select value={whisperChar} onChange={e => setWhisperChar(e.target.value)}>
                    {data.characters.map(char => <option key={char.id} value={char.id}>{char.name}</option>)}
                </select>
                <textarea value={whisperText} onChange={e => setWhisperText(e.target.value)} rows="4" placeholder="Короткое видение, личный секрет, знак судьбы..." />
                <button className="btn-mystic" onClick={sendWhisper}>👁 Отправить шёпот</button>
            </SectionCard>

            <SectionCard title="Журнал сцены" subtitle="Последние решения и движение мира" fullWidth>
                <div className="admin-timeline">
                    {data.events.length > 0 ? data.events.map((event, idx) => (
                        <div key={idx} className="admin-timeline-item">{event}</div>
                    )) : <div className="admin-empty-state">Сцена ещё не записала ни одного события.</div>}
                </div>
            </SectionCard>
        </div>
    );

    const renderPlayers = () => (
        <div>
            <div className="admin-overview-strip">
                <MetricCard label="Героев" value={`${data.characters.length}`} hint="Активные карточки персонажей" />
                <MetricCard label="Spotlight" value={spotlight === 'ALL' ? 'Общий' : spotlight} hint="Кто сейчас определяет кадр" />
                <MetricCard label="Шёпот" value={whisperChar || 'Не выбран'} hint="Быстрый адресат секретов" />
            </div>
            <div className="admin-player-grid">
                {data.characters.map(char => <AdminCharacterCard key={char.id} c={char} />)}
            </div>
        </div>
    );

    const renderBackstage = () => (
        <div className="admin-dashboard-grid admin-dashboard-grid--two">
            <SectionCard title="Разум и каналы" subtitle="Служебные настройки без вмешательства в сюжет">
                <span className="stat-label">Режим мозга</span>
                <select value={llmTier} onChange={(e) => updateLlmTier(e.target.value)}>
                    <option value="free">Free (экономный)</option>
                    <option value="paid">Paid (Gemini only)</option>
                </select>
                <span className="stat-label">Модель</span>
                <select value={model} onChange={(e) => updateModel(e.target.value)}>
                    {availableModels.map(m => (
                        <option key={m.id} value={m.id}>[{m.provider}] {m.name}</option>
                    ))}
                </select>
                <div className="admin-world-card-note" style={{ marginTop: '8px' }}>
                    {llmTier === 'paid'
                        ? 'Paid: разрешены только модели Gemini с вашим API-ключом.'
                        : 'Free: доступны Gemini + альтернативные провайдеры (если подключены).'}
                </div>
                <div className="admin-note-box" style={{ marginTop: '14px' }}>
                    <div className="admin-note-title">Подключённые группы</div>
                    {data.groups?.length ? data.groups.map(group => (
                        <div key={group.id} className="admin-group-row">
                            <span>{group.title || 'Без названия'}</span>
                            <span style={{ color: group.status === 'OK' ? '#86efac' : '#ff8585' }}>{group.status || '?'}</span>
                        </div>
                    )) : <p>Бот ещё не добавлен в группы.</p>}
                </div>
            </SectionCard>

            <SectionCard title="Статус режиссуры" subtitle="Только чтение" >
                <div className="admin-raw-state">
                    <div><b>Последний мировой ход:</b> {ws.last_world_event || 'Нет'}</div>
                    <div><b>Последний бит:</b> {ws.director_last_beat || 'Нет'}</div>
                    <div><b>Фаза:</b> {ws.scene_phase || 'Нет'}</div>
                    <div><b>Фокус:</b> {ws.director_focus || 'Нет'}</div>
                    <div><b>Переход акта:</b> {ws.director_should_end_scene === '1' ? 'Сцена созрела' : 'Сцена продолжается'}</div>
                </div>
            </SectionCard>

            <SectionCard title="Кнопка конца света" subtitle="Крайнее средство" fullWidth tone="danger">
                <div className="admin-note-box admin-note-box--danger">
                    <div className="admin-note-title">Осторожно</div>
                    <p>Это уничтожит текущий виток судьбы, обнулит память, вещи, clocks и реакции мира.</p>
                </div>
                <button className="btn-danger" onClick={resetGame}>🔥 УНИЧТОЖИТЬ ЭТОТ МИР</button>
            </SectionCard>
        </div>
    );

    return (
        <div>
            <div style={{ textAlign: 'center', marginBottom: '24px' }}>
                <h2 style={{ fontSize: '1.8rem', textShadow: '0 0 20px var(--accent-color)' }}>Око Многоликого</h2>
                <small style={{ color: '#aaa', letterSpacing: '2px' }}>Центр управления сессией</small>
            </div>

            <div className="admin-nav-tabs">
                {VIEW_TABS.map(tab => (
                    <button
                        key={tab.id}
                        className={`admin-nav-tab ${activeView === tab.id ? 'active' : ''}`}
                        onClick={() => setActiveView(tab.id)}
                        type="button"
                    >
                        <span>{tab.icon}</span>
                        <span>{tab.label}</span>
                    </button>
                ))}
            </div>

            {activeView === 'overview' && renderOverview()}
            {activeView === 'scene' && renderScene()}
            {activeView === 'players' && renderPlayers()}
            {activeView === 'backstage' && renderBackstage()}
        </div>
    );
}

function SectionCard({ title, subtitle, children, fullWidth = false, tone = 'default' }) {
    return (
        <section className={`card admin-section-card admin-section-card--${tone} ${fullWidth ? 'admin-section-card--full' : ''}`}>
            <div className="admin-section-head">
                <div>
                    <h3>{title}</h3>
                    {subtitle && <p>{subtitle}</p>}
                </div>
            </div>
            {children}
        </section>
    );
}

function MetricCard({ label, value, hint, wide = false }) {
    return (
        <div className={`admin-metric-card ${wide ? 'admin-metric-card--wide' : ''}`}>
            <div className="admin-metric-label">{label}</div>
            <div className="admin-metric-value">{value}</div>
            {hint && <div className="admin-metric-hint">{hint}</div>}
        </div>
    );
}

function ModePill({ active, onClick, icon, title, subtitle, compact = false }) {
    return (
        <button type="button" className={`admin-mode-pill ${active ? 'active' : ''} ${compact ? 'compact' : ''}`} onClick={onClick}>
            <div className="admin-mode-icon">{icon}</div>
            <div>
                <div className="admin-mode-title">{title}</div>
                <div className="admin-mode-subtitle">{subtitle}</div>
            </div>
        </button>
    );
}

function ChoiceChip({ active, onClick, children }) {
    return (
        <button type="button" className={`admin-choice-chip ${active ? 'active' : ''}`} onClick={onClick}>
            {children}
        </button>
    );
}

function QuickActionButton({ title, hint, onClick }) {
    return (
        <button type="button" className="admin-quick-action" onClick={onClick}>
            <span>{title}</span>
            <small>{hint}</small>
        </button>
    );
}

function AdminCharacterCard({ c }) {
    const hpP = Math.max(0, Math.min(100, (c.hp / c.max_hp) * 100));
    const strP = Math.max(0, Math.min(100, c.stress));

    return (
        <details className="card admin-character-card" open={false}>
            <summary>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <b style={{ color: 'var(--accent-hover)', fontSize: '1.05rem' }}>{c.name}</b>
                    <small style={{ color: '#777' }}>HP {c.hp}/{c.max_hp} · Стресс {c.stress}</small>
                </div>
            </summary>

            <div className="admin-character-body">
                <div className="stat-label">Состояние</div>
                <div className="stat-bar-container"><div className="stat-bar hp-bar" style={{ width: `${hpP}%` }}></div></div>
                <div className="stat-bar-container"><div className="stat-bar stress-bar" style={{ width: `${strP}%` }}></div></div>

                <div className="admin-field-grid">
                    <div>
                        <span className="stat-label">Имя</span>
                        <div className="admin-world-card-note"><b>{c.name}</b></div>
                    </div>
                    <div>
                        <span className="stat-label">Telegram ID</span>
                        <div className="admin-world-card-note">{c.tg_id || 'не привязан'}</div>
                    </div>
                </div>

                <div className="admin-field-grid">
                    <div>
                        <span className="stat-label">HP</span>
                        <div className="admin-world-card-note">{c.hp}/{c.max_hp}</div>
                    </div>
                    <div>
                        <span className="stat-label">Стресс</span>
                        <div className="admin-world-card-note">{c.stress}</div>
                    </div>
                </div>

                <span className="stat-label">Инвентарь</span>
                <div>
                    {c.items.length > 0 ? c.items.map(item => (
                        <span key={item} className="item-tag">{item}</span>
                    )) : <div className="admin-empty-state">Пусто</div>}
                </div>

                <span className="stat-label">Тайны персонажа</span>
                <div>
                    {c.knowledge && c.knowledge.length > 0 ? c.knowledge.map(entry => (
                        <div key={`${c.id}_${entry.title}`} className="knowledge-block">
                            <b style={{ color: 'var(--accent-hover)' }}>{entry.title}</b>
                            <div style={{ color: '#ccc' }}>{entry.content}</div>
                        </div>
                    )) : <div className="admin-empty-state">Пока нет</div>}
                </div>
            </div>
        </details>
    );
}
