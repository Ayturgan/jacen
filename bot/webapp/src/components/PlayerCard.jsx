import { useState, useEffect, useRef } from 'react';
import { safeTGAction } from '../api';

export default function PlayerCard({ data, onRollDice }) {
    const char = data.character;
    const ws = data.world_state;
    const whispers = data.whispers || [];
    const hpP = Math.max(0, Math.min(100, (char.hp / char.max_hp) * 100));
    const strP = Math.max(0, Math.min(100, (char.stress / 100) * 100));

    const [activeTab, setActiveTab] = useState('bio');
    const [imgModal, setImgModal] = useState(null);
    const [lore, setLore] = useState(null);
    const isQuestPaused = ws.quest_paused === '1';
    const isInGame = ws.bot_mode === 'quest' && ws.quest_started === '1' && !isQuestPaused;
    const pendingRollForMe = ws.pending_roll_char === char.id;
    const playerStateLabel = isQuestPaused ? 'Пауза' : isInGame ? 'В игре' : 'Вне игры';
    const playerStateColor = isQuestPaused ? '#fbbf24' : isInGame ? '#86efac' : '#888';

    useEffect(() => {
        fetch(`/api/lore/${char.id}`)
            .then(r => r.json())
            .then(d => { if (d.status === 'ok') setLore(d.lore); })
            .catch(e => console.error(e));
    }, [char.id]);

    let charStatus = char.status;
    if (!charStatus) {
        if (hpP <= 20) charStatus = "При смерти";
        else if (strP >= 80) charStatus = "На грани безумия";
        else charStatus = "Исследователь";
    }

    const switchTab = (tab) => {
        setActiveTab(tab);
        safeTGAction(t => t.HapticFeedback.selectionChanged());
    };

    const handleImgClick = () => {
        if (char.avatar_url) {
            setImgModal(char.avatar_url);
            safeTGAction(t => t.HapticFeedback.impactOccurred('light'));
        }
    };

    const closeImg = () => setImgModal(null);

    return (
        <div>
            {imgModal && (
                <div id="image-modal" className="active" style={{ display: 'flex' }} onClick={closeImg}>
                    <img id="modal-img" src={imgModal} alt="Avatar" />
                </div>
            )}

            <div className="card">
                <div className="header-flex">
                    <div className="avatar-wrap" onClick={handleImgClick}>
                        {char.avatar_url ? (
                            <img src={char.avatar_url} className="avatar" />
                        ) : (
                            <div className="avatar" style={{ background: 'radial-gradient(#333, #111)', display: 'flex', justifyContent: 'center', alignItems: 'center', fontFamily: 'Cinzel', fontSize: '2rem', color: '#555' }}>?</div>
                        )}
                    </div>
                    <div>
                        <h2>{char.name}</h2>
                        <small style={{ color: 'var(--accent-color)', opacity: 0.8, fontStyle: 'italic' }}>{charStatus}</small>
                        <div style={{ marginTop: '8px' }}>
                            <span style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '6px 10px',
                                borderRadius: '999px',
                                background: isInGame ? 'rgba(74,222,128,0.12)' : 'rgba(255,255,255,0.06)',
                                border: `1px solid ${isInGame ? 'rgba(74,222,128,0.28)' : 'rgba(255,255,255,0.08)'}`,
                                color: playerStateColor,
                                fontSize: '0.75rem',
                                textTransform: 'uppercase',
                                letterSpacing: '1px'
                            }}>
                                {isQuestPaused ? '⏸' : isInGame ? '🟢' : '⚪'} {playerStateLabel}
                            </span>
                        </div>
                    </div>
                </div>

                <span className="stat-label">Жизненная сила <span style={{ color: '#ff6b6b' }}>({char.hp}/{char.max_hp})</span></span>
                <div className="stat-bar-container"><div className="stat-bar hp-bar" style={{ width: `${hpP}%` }}></div></div>

                <span className="stat-label">Влияние тени (Стресс) <span style={{ color: '#d0bfff' }}>({char.stress}%)</span></span>
                <div className="stat-bar-container"><div className="stat-bar stress-bar" style={{ width: `${strP}%` }}></div></div>
            </div>

            {isQuestPaused && (
                <div
                    className="card"
                    style={{
                        border: '1px solid rgba(251,191,36,0.38)',
                        background: 'linear-gradient(135deg, rgba(251,191,36,0.10) 0%, rgba(20,15,25,0.96) 100%)',
                        boxShadow: '0 0 22px rgba(251,191,36,0.14)',
                        marginTop: '14px'
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
                        <div style={{ fontSize: '1.5rem' }}>⏸</div>
                        <div>
                            <div style={{ color: '#fbbf24', fontFamily: "'Cinzel', serif", letterSpacing: '1px', textTransform: 'uppercase' }}>
                                Квест на паузе
                            </div>
                            <div style={{ color: '#e7d7a2', fontSize: '0.9rem', marginTop: '4px' }}>
                                Якен запомнил место разрыва сцены и будет ждать команды на продолжение.
                            </div>
                        </div>
                    </div>
                    <div style={{ color: '#ccc', lineHeight: '1.6', fontSize: '0.95rem' }}>
                        <div><b style={{ color: '#f4df9d' }}>Причина:</b> {ws.quest_pause_reason || 'Игроки решили остановиться здесь и вернуться позже.'}</div>
                        <div style={{ marginTop: '8px' }}><b style={{ color: '#f4df9d' }}>Что дальше:</b> ГМ может продолжить ту же сцену позже, и история пойдёт с сохранённого места.</div>
                    </div>
                </div>
            )}

            {/* TABS */}
            <div className="tabs">
                <div className={`tab ${activeTab === 'bio' ? 'active' : ''}`} onClick={() => switchTab('bio')}>Персонаж</div>
                <div className={`tab ${activeTab === 'inv' ? 'active' : ''}`} onClick={() => switchTab('inv')}>Сумка</div>
                <div className={`tab ${activeTab === 'map' ? 'active' : ''}`} onClick={() => switchTab('map')}>Карта</div>
                <div className={`tab ${activeTab === 'lore' ? 'active' : ''}`} onClick={() => switchTab('lore')}>Гримуар</div>
                <div className={`tab ${activeTab === 'visions' ? 'active' : ''}`} onClick={() => switchTab('visions')}>
                    Видения {whispers.length > 0 && <span style={{ display: 'inline-block', background: 'var(--mystery)', color: '#fff', borderRadius: '50%', width: '18px', height: '18px', fontSize: '0.7rem', lineHeight: '18px', textAlign: 'center', marginLeft: '5px' }}>{whispers.length}</span>}
                </div>
            </div>

            {/* ===== TAB: ПЕРСОНАЖ ===== */}
            {activeTab === 'bio' && (
                <div className="card tab-content active" style={{ minHeight: '200px' }}>
                    {lore ? (
                        <div>
                            {/* Цитата */}
                            <div style={{ padding: '15px 20px', background: 'rgba(201, 162, 39, 0.05)', borderLeft: '3px solid var(--accent-color)', borderRadius: '0 8px 8px 0', marginBottom: '20px', fontStyle: 'italic', color: '#ccc', lineHeight: '1.6' }}>
                                {lore.quote}
                            </div>

                            {/* Основные данные */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
                                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
                                    <div style={{ fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>Роль</div>
                                    <div style={{ color: 'var(--accent-hover)', fontSize: '0.85rem', fontFamily: "'Cinzel', serif" }}>{lore.role}</div>
                                </div>
                                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
                                    <div style={{ fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>Возраст</div>
                                    <div style={{ color: 'var(--accent-hover)', fontSize: '0.85rem', fontFamily: "'Cinzel', serif" }}>{lore.age}</div>
                                </div>
                                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)', gridColumn: 'span 2' }}>
                                    <div style={{ fontSize: '0.7rem', color: '#888', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>Происхождение</div>
                                    <div style={{ color: '#ccc', fontSize: '0.9rem' }}>{lore.origin}</div>
                                </div>
                            </div>

                            {/* Внешность */}
                            <details open style={{ marginBottom: '15px' }}>
                                <summary style={{ color: 'var(--accent-color)', fontFamily: "'Cinzel', serif", fontSize: '0.95rem', padding: '8px 0' }}>
                                    🪞 Внешность
                                </summary>
                                <p style={{ color: '#bbb', lineHeight: '1.6', margin: '10px 0', paddingLeft: '10px' }}>{lore.appearance}</p>
                            </details>

                            {/* Артефакт */}
                            <div style={{ background: 'linear-gradient(135deg, rgba(201,162,39,0.08) 0%, rgba(157,78,221,0.08) 100%)', padding: '15px', borderRadius: '12px', border: '1px solid rgba(201,162,39,0.2)', marginBottom: '15px' }}>
                                <div style={{ fontSize: '0.75rem', color: 'var(--accent-color)', textTransform: 'uppercase', letterSpacing: '2px', marginBottom: '8px', fontFamily: "'Cinzel', serif" }}>✧ Особая деталь</div>
                                <p style={{ color: '#ddd', lineHeight: '1.5', margin: 0 }}>{lore.artifact}</p>
                            </div>

                            {/* Предыстория */}
                            <details style={{ marginBottom: '15px' }}>
                                <summary style={{ color: 'var(--accent-color)', fontFamily: "'Cinzel', serif", fontSize: '0.95rem', padding: '8px 0' }}>
                                    📜 Твоя история
                                </summary>
                                <div style={{ padding: '15px', background: 'rgba(0,0,0,0.3)', borderRadius: '10px', marginTop: '10px', borderLeft: '3px solid var(--mystery)' }}>
                                    <p style={{ color: '#ccc', lineHeight: '1.7', margin: 0 }}>{lore.backstory}</p>
                                </div>
                            </details>

                            {/* Навыки */}
                            <details style={{ marginBottom: '15px' }}>
                                <summary style={{ color: 'var(--accent-color)', fontFamily: "'Cinzel', serif", fontSize: '0.95rem', padding: '8px 0' }}>
                                    ⚔️ Навыки и Способности
                                </summary>
                                <div style={{ marginTop: '10px' }}>
                                    {lore.skills.map((skill, i) => (
                                        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '10px 12px', background: i % 2 === 0 ? 'rgba(0,0,0,0.2)' : 'transparent', borderRadius: '8px', marginBottom: '4px' }}>
                                            <span style={{ color: 'var(--accent-color)', fontSize: '1.1rem', flexShrink: 0 }}>◆</span>
                                            <span style={{ color: '#ccc', fontSize: '0.9rem', lineHeight: '1.4' }}>{skill}</span>
                                        </div>
                                    ))}
                                </div>
                            </details>

                            {/* Связи */}
                            <div style={{ background: 'rgba(157,78,221,0.08)', padding: '15px', borderRadius: '12px', border: '1px solid rgba(157,78,221,0.2)', marginBottom: '15px' }}>
                                <div style={{ fontSize: '0.75rem', color: '#d0bfff', textTransform: 'uppercase', letterSpacing: '2px', marginBottom: '8px', fontFamily: "'Cinzel', serif" }}>🤝 Связи</div>
                                <p style={{ color: '#ccc', lineHeight: '1.5', margin: 0 }}>{lore.bonds}</p>
                            </div>

                            {/* Цель */}
                            <div style={{ background: 'rgba(217,4,41,0.06)', padding: '15px', borderRadius: '12px', border: '1px solid rgba(217,4,41,0.15)' }}>
                                <div style={{ fontSize: '0.75rem', color: '#ff6b6b', textTransform: 'uppercase', letterSpacing: '2px', marginBottom: '8px', fontFamily: "'Cinzel', serif" }}>🎯 Твоя цель</div>
                                <p style={{ color: '#ddd', lineHeight: '1.5', margin: 0, fontStyle: 'italic' }}>{lore.goal}</p>
                            </div>
                        </div>
                    ) : (
                        <div style={{ textAlign: 'center', padding: '40px 0', color: '#666' }}>
                            <div className="d20-wrapper loading" style={{ width: '40px', height: '40px', margin: '0 auto 15px' }}>
                                <svg viewBox="0 0 100 100" className="d20-svg"><polygon points="50,5 90,25 90,75 50,95 10,75 10,25" /></svg>
                            </div>
                            Свитки разворачиваются...
                        </div>
                    )}
                </div>
            )}

            {/* ===== TAB: ИНВЕНТАРЬ ===== */}
            {activeTab === 'inv' && (
                <div className="card tab-content active" style={{ minHeight: '150px' }}>
                    {char.items.length > 0
                        ? char.items.map(i => <span key={i} className="item-tag">{i}</span>)
                        : <p style={{ textAlign: 'center', color: '#666', fontStyle: 'italic', marginTop: '20px' }}>Сумка пуста. Лишь ветер гуляет внутри.</p>}
                </div>
            )}

            {/* ===== TAB: КАРТА ЭССОСА ===== */}
            {activeTab === 'map' && (
                <div className="card tab-content active" style={{ padding: '10px' }}>
                    <InteractiveMap currentLocation={ws.current_location} />
                    <div style={{ textAlign: 'center', marginTop: '10px' }}>
                        <span style={{ color: 'var(--accent-color)', fontSize: '0.8rem', fontFamily: "'Cinzel', serif" }}>
                            🗺 Твоё местоположение: <b>{ws.current_location || 'Неизвестно'}</b>
                        </span>
                    </div>
                </div>
            )}

            {/* ===== TAB: ГРИМУАР ===== */}
            {activeTab === 'lore' && (
                <div className="card tab-content active" style={{ minHeight: '150px' }}>
                    {char.knowledge.length > 0
                        ? char.knowledge.map(k => (
                            <div key={k.title} className="knowledge-block">
                                <b style={{ color: 'var(--accent-hover)', display: 'block', marginBottom: '5px', fontFamily: "'Cinzel', serif" }}>📜 {k.title}</b>
                                <span style={{ color: '#ccc' }}>{k.content}</span>
                            </div>
                        ))
                        : <p style={{ textAlign: 'center', color: '#666', fontStyle: 'italic', marginTop: '20px' }}>Разум чист. Тайны еще скрыты во мраке.</p>}
                </div>
            )}

            {/* ===== TAB: ВИДЕНИЯ (Архив шепотов) ===== */}
            {activeTab === 'visions' && (
                <div className="card tab-content active" style={{ minHeight: '150px' }}>
                    <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                        <h3 style={{ color: '#d0bfff', fontFamily: "'Cinzel', serif", fontSize: '1rem', textShadow: '0 0 15px var(--mystery)' }}>Архив Видений</h3>
                        <small style={{ color: '#777' }}>Шёпоты Судьбы, что пронзали твой разум</small>
                    </div>

                    {whispers.length > 0 ? (
                        <div>
                            {whispers.map((w, idx) => (
                                <div key={idx} style={{
                                    padding: '15px',
                                    background: 'linear-gradient(135deg, rgba(157,78,221,0.08) 0%, rgba(0,0,0,0.3) 100%)',
                                    borderLeft: '3px solid var(--mystery)',
                                    borderRadius: '0 10px 10px 0',
                                    marginBottom: '12px',
                                    position: 'relative',
                                    overflow: 'hidden'
                                }}>
                                    <div style={{ position: 'absolute', top: 0, right: 0, bottom: 0, width: '30%', background: 'linear-gradient(90deg, transparent, rgba(157,78,221,0.03))', pointerEvents: 'none' }}></div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                                        <span style={{ fontSize: '1.1rem' }}>👁</span>
                                        <span style={{ fontSize: '0.7rem', color: '#9d4edd', textTransform: 'uppercase', letterSpacing: '1px', fontFamily: "'Cinzel', serif" }}>Видение</span>
                                        {w.timestamp && <span style={{ fontSize: '0.65rem', color: '#555', marginLeft: 'auto' }}>{new Date(w.timestamp + 'Z').toLocaleDateString('ru-RU')}</span>}
                                    </div>
                                    <p style={{ color: '#d0bfff', lineHeight: '1.6', margin: 0, fontStyle: 'italic' }}>{w.text}</p>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div style={{ textAlign: 'center', padding: '30px 0' }}>
                            <div style={{ fontSize: '2.5rem', marginBottom: '15px', opacity: 0.3 }}>👁</div>
                            <p style={{ color: '#555', fontStyle: 'italic' }}>Пустота. Мрак ещё не обращался к тебе.</p>
                        </div>
                    )}
                </div>
            )}

            <button className="btn-action" onClick={onRollDice} style={{ marginTop: '10px', fontSize: '1rem', padding: '16px' }}>
                {pendingRollForMe ? '🎲 Ответить на зов судьбы' : isInGame ? '🎲 Бросить кости судьбы' : '🎲 Бросить кости вне сюжета'}
            </button>
        </div>
    );
}

function InteractiveMap({ currentLocation }) {
    const viewportRef = useRef(null);
    const [scale, setScale] = useState(1.2);
    const [offset, setOffset] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [lastPos, setLastPos] = useState({ x: 0, y: 0 });
    const [lastDist, setLastDist] = useState(0);

    const MAP_LOCATIONS = {
        "Braavos": { x: 9.3, y: 7.8, name: "Браавос" },
        "Браавос": { x: 9.3, y: 7.8, name: "Браавос" },
        "Volantis": { x: 34.6, y: 66.2, name: "Волантис" },
        "Волантис": { x: 34.6, y: 66.2, name: "Волантис" },
        "Meereen": { x: 71.8, y: 57.2, name: "Миэрин" },
        "Миэрин": { x: 71.8, y: 57.2, name: "Миэрин" },
        "Valyria": { x: 44.5, y: 89.2, name: "Валирия" },
        "Валирия": { x: 44.5, y: 89.2, name: "Валирия" },
        "Pentos": { x: 10.2, y: 34.3, name: "Пентос" },
        "Пентос": { x: 10.2, y: 34.3, name: "Пентос" },
        "Lys": { x: 11.2, y: 68.3, name: "Лисс" },
        "Лисс": { x: 11.2, y: 68.3, name: "Лисс" },
        "Astapor": { x: 67.1, y: 71.9, name: "Астапор" },
        "Астапор": { x: 67.1, y: 71.9, name: "Астапор" },
        "Yunkai": { x: 70.4, y: 63.8, name: "Юнкай" },
        "Юнкай": { x: 70.4, y: 63.8, name: "Юнкай" },
        "Qohor": { x: 35.2, y: 35.1, name: "Квохор" },
        "Квохор": { x: 35.2, y: 35.1, name: "Квохор" },
        "Tyrosh": { x: 5.6, y: 51.5, name: "Тирош" },
        "Тирош": { x: 5.6, y: 51.5, name: "Тирош" },
        "Myr": { x: 14.8, y: 50.4, name: "Мир" },
        "Мир": { x: 14.8, y: 50.4, name: "Мир" },
        "Selhorys": { x: 31.4, y: 51.5, name: "Селхорис" },
        "Селхорис": { x: 31.4, y: 51.5, name: "Селхорис" },
        "Elyria": { x: 51.4, y: 67.2, name: "Элирия" },
        "Элирия": { x: 51.4, y: 67.2, name: "Элирия" },
        "Road of Bones": { x: 36.2, y: 48.1, name: "Дорога Костей" },
        "Дорога Костей": { x: 36.2, y: 48.1, name: "Дорога Костей" },
        "Dead Oasis": { x: 58.4, y: 58.2, name: "Мертвый Оазис" },
        "Мертвый Оазис": { x: 58.4, y: 58.2, name: "Мертвый Оазис" },
        "Ash Sea": { x: 48.2, y: 78.5, name: "Пепельное Море" },
        "Пепельное Море": { x: 48.2, y: 78.5, name: "Пепельное Море" },
        "Ruins of Theris": { x: 42.1, y: 86.4, name: "Руины Тайэриса" },
        "Руины Тайэриса": { x: 42.1, y: 86.4, name: "Руины Тайэриса" }
    };

    const target = MAP_LOCATIONS[currentLocation];

    const constrainOffset = (val, s) => {
        const bound = (s - 1) * 50 / s;
        return Math.min(Math.max(val, -bound), bound);
    };

    const handleWheel = (e) => {
        const delta = e.deltaY * -0.001;
        const newScale = Math.min(Math.max(scale + delta, 1), 5);
        setScale(newScale);
        setOffset(prev => ({
            x: constrainOffset(prev.x, newScale),
            y: constrainOffset(prev.y, newScale)
        }));
    };

    const handleStart = (clientX, clientY) => {
        setIsDragging(true);
        setLastPos({ x: clientX, y: clientY });
    };

    const handleMove = (clientX, clientY) => {
        if (!isDragging || !viewportRef.current) return;
        const rect = viewportRef.current.getBoundingClientRect();
        const dx = ((clientX - lastPos.x) / rect.width) * 100 / scale;
        const dy = ((clientY - lastPos.y) / rect.height) * 100 / scale;

        setOffset(prev => ({
            x: constrainOffset(prev.x + dx, scale),
            y: constrainOffset(prev.y + dy, scale)
        }));
        setLastPos({ x: clientX, y: clientY });
    };

    const handleTouchStart = (e) => {
        if (e.touches.length === 2) {
            const dist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
            setLastDist(dist);
            setIsDragging(false);
        } else {
            handleStart(e.touches[0].clientX, e.touches[0].clientY);
        }
    };

    const handleTouchMove = (e) => {
        if (e.touches.length === 2) {
            const dist = Math.hypot(
                e.touches[0].clientX - e.touches[1].clientX,
                e.touches[0].clientY - e.touches[1].clientY
            );
            if (lastDist > 0) {
                const delta = (dist - lastDist) * 0.01;
                const newScale = Math.min(Math.max(scale + delta, 1), 5);
                setScale(newScale);
                setOffset(prev => ({
                    x: constrainOffset(prev.x, newScale),
                    y: constrainOffset(prev.y, newScale)
                }));
            }
            setLastDist(dist);
        } else {
            handleMove(e.touches[0].clientX, e.touches[0].clientY);
        }
    };

    const handleEnd = () => {
        setIsDragging(false);
        setLastDist(0);
    };

    useEffect(() => {
        if (target) {
            const s = 1.5;
            setScale(s);
            // Формула для центрирования: (50/s - tx) выравнивает tx по центру
            setOffset({
                x: constrainOffset(50 / s - target.x, s),
                y: constrainOffset(50 / s - target.y, s)
            });
        }
    }, [currentLocation]);

    return (
        <div className="map-viewport" ref={viewportRef}>
            <div
                className="map-pan-zoom"
                onMouseDown={(e) => handleStart(e.clientX, e.clientY)}
                onMouseMove={(e) => handleMove(e.clientX, e.clientY)}
                onMouseUp={handleEnd}
                onMouseLeave={handleEnd}
                onWheel={handleWheel}
                onTouchStart={handleTouchStart}
                onTouchMove={handleTouchMove}
                onTouchEnd={handleEnd}
            >
                <div style={{
                    position: 'absolute',
                    width: '100%',
                    height: '100%',
                    transform: `scale(${scale}) translate(${offset.x}%, ${offset.y}%)`,
                    transition: isDragging ? 'none' : 'transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1)',
                    transformOrigin: 'center center'
                }}>
                    <img
                        src="/static/essos_map.png"
                        className="map-image"
                        style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.9 }}
                    />

                    {target && (
                        <div
                            className="map-marker"
                            style={{
                                left: `${target.x}%`,
                                top: `${target.y}%`,
                                transform: `translate(-50%, -50%) scale(${1 / scale})`
                            }}
                        >
                            <div className="marker-pulse"></div>
                            <div className="marker-label">ТЫ ЗДЕСЬ</div>
                        </div>
                    )}
                </div>
            </div>

            <div className="map-controls">
                <button className="map-btn" onClick={() => {
                    const newScale = Math.min(scale + 0.5, 5);
                    setScale(newScale);
                    setOffset(prev => ({ x: constrainOffset(prev.x, newScale), y: constrainOffset(prev.y, newScale) }));
                }}>+</button>
                <button className="map-btn" onClick={() => {
                    const newScale = Math.max(scale - 0.5, 1);
                    setScale(newScale);
                    setOffset(prev => ({ x: constrainOffset(prev.x, newScale), y: constrainOffset(prev.y, newScale) }));
                }}>-</button>
            </div>
        </div>
    );
}
