import { useState, useEffect } from 'react';

export default function IntroScreen({ onComplete }) {
    const [started, setStarted] = useState(false);
    const [lines, setLines] = useState(Array(7).fill({ show: false, done: false }));
    const [skipping, setSkipping] = useState(false);
    const [visible, setVisible] = useState(true);
    const [showSkip, setShowSkip] = useState(false);

    useEffect(() => {
        if (!started || skipping) return;

        let timeouts = [];
        let currentDelay = 500;
        
        timeouts.push(setTimeout(() => setShowSkip(true), 3000));

        for (let i = 0; i < 7; i++) {
            const displayTime = i === 5 ? 4000 : 3500;
            
            timeouts.push(setTimeout(() => {
                setLines(prev => {
                    const next = [...prev];
                    next[i] = { show: true, done: false };
                    return next;
                });
            }, currentDelay));

            if (i < 6) {
                timeouts.push(setTimeout(() => {
                    setLines(prev => {
                        const next = [...prev];
                        next[i] = { show: false, done: true };
                        return next;
                    });
                }, currentDelay + displayTime));
                currentDelay += displayTime + 1500;
            } else {
                currentDelay += displayTime;
            }
        }

        timeouts.push(setTimeout(() => finishIntro(), currentDelay + 2000));

        return () => timeouts.forEach(clearTimeout);
    }, [started, skipping]);

    const startIntro = () => {
        setStarted(true);
        const music = document.getElementById('bg-music');
        if(music) {
            music.volume = 0.3;
            music.play().catch(e => console.log("Audio play blocked", e));
        }
    };

    const finishIntro = () => {
        setSkipping(true);
        setVisible(false);
        setTimeout(() => {
            onComplete();
        }, 2000); // Wait for fade out
    };

    if (!visible) return null;

    return (
        <div id="intro-screen" style={{ opacity: skipping ? 0 : 1, display: 'flex' }}>
            <div style={{ position: 'relative', width: '100%', height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 0, margin: 0 }}>
                {!started && <button id="intro-btn" onClick={startIntro}>Принять судьбу</button>}
                
                <div className={`intro-text-line ${lines[0].show ? 'show' : ''}`} style={{ display: lines[0].done ? 'none' : 'block' }}>Минуло сорок лет с тех пор, как стихли битвы за Железный Трон...</div>
                <div className={`intro-text-line ${lines[1].show ? 'show' : ''}`} style={{ display: lines[1].done ? 'none' : 'block' }}>Драконы исчезли. Но их эхо вновь пробуждается в песках Эссоса.</div>
                <div className={`intro-text-line ${lines[2].show ? 'show' : ''}`} style={{ display: lines[2].done ? 'none' : 'block' }}>Тайные ордены ведут незримую войну, пытаясь подчинить себе древние пророчества...</div>
                <div className={`intro-text-line ${lines[3].show ? 'show' : ''}`} style={{ display: lines[3].done ? 'none' : 'block' }}>Магия возвращается, но не как благословение...<br/>А как гибельное искажение.</div>
                <div className={`intro-text-line ${lines[4].show ? 'show' : ''}`} style={{ display: lines[4].done ? 'none' : 'block' }}>Сможешь ли ты выдержать бремя Печати?</div>
                <div className={`intro-text-line ${lines[5].show ? 'show' : ''}`} style={{ display: lines[5].done ? 'none' : 'block', fontSize: '1.6rem', color: '#ff4444', textShadow: '0 0 30px rgba(255,0,0,0.8)' }}>ЭХО ДРАКОНЬЕЙ КРОВИ</div>
                <div className={`intro-text-line ${lines[6].show ? 'show' : ''}`} style={{ display: lines[6].done ? 'none' : 'block' }}>Кем в этом мире станешь ТЫ?</div>
            </div>
            {started && <div id="intro-skip" className={showSkip ? 'show' : ''} onClick={finishIntro}>Пропустить</div>}
        </div>
    );
}
