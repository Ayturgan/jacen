import { useState, useEffect } from 'react';
import { safeFetch, safeTGAction } from './api';
import IntroScreen from './components/IntroScreen';
import AdminPanel from './components/AdminPanel';
import PlayerCard from './components/PlayerCard';
import DiceRoller from './components/DiceRoller';

export default function App() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showIntro, setShowIntro] = useState(false);
    const [diceActive, setDiceActive] = useState(false);
    const [musicPlaying, setMusicPlaying] = useState(true);

    useEffect(() => {
        safeTGAction(t => {
            t.ready();
            t.expand();
            t.setHeaderColor('#050505');
            t.setBackgroundColor('#050505');
        });

        const hasSeenIntro = localStorage.getItem('introSeen_echo');
        if (!hasSeenIntro) {
            setShowIntro(true);
        } else {
            loadData();
        }
    }, []);

    useEffect(() => {
        if (showIntro || loading) return undefined;

        const intervalId = setInterval(() => {
            loadData();
        }, 4000);

        return () => clearInterval(intervalId);
    }, [showIntro, loading]);

    const loadData = async () => {
        const urlParams = new URLSearchParams(window.location.search);
        let tgUserId = 0;
        safeTGAction(t => {
            if(t.initDataUnsafe?.user?.id) tgUserId = t.initDataUnsafe.user.id;
        });
        const userId = tgUserId || parseInt(urlParams.get('uid')) || 0;
        
        try {
            const response = await fetch(`/api/user/${userId}`);
            const result = await response.json();
            setData(result);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleIntroComplete = () => {
        localStorage.setItem('introSeen_echo', 'true');
        setShowIntro(false);
        setLoading(true);
        loadData();
    };

    useEffect(() => {
        if (data && data.role === 'player' && data.character) {
            const char = data.character;
            if (char.hp / char.max_hp <= 0.2) document.body.classList.add('critical-hp');
            else document.body.classList.remove('critical-hp');
            
            if (char.stress >= 80) document.body.classList.add('high-stress');
            else document.body.classList.remove('high-stress');
        }
    }, [data]);

    if (showIntro) {
        return <IntroScreen onComplete={handleIntroComplete} />;
    }

    if (loading) {
        return (
            <div style={{ height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', flexDirection: 'column' }}>
                <div className="d20-wrapper loading" style={{ width: '80px', height: '80px' }}>
                    <svg viewBox="0 0 100 100" className="d20-svg">
                        <polygon points="50,5 90,25 90,75 50,95 10,75 10,25" />
                        <polygon points="25,35 75,35 50,80" className="glass-face"/>
                        <line x1="50" y1="5" x2="25" y2="35" /><line x1="50" y1="5" x2="75" y2="35" />
                        <line x1="90" y1="25" x2="75" y2="35" /><line x1="90" y1="75" x2="75" y2="35" />
                        <line x1="90" y1="75" x2="50" y2="80" /><line x1="50" y1="95" x2="50" y2="80" />
                        <line x1="10" y1="75" x2="50" y2="80" /><line x1="10" y1="75" x2="25" y2="35" />
                        <line x1="10" y1="25" x2="25" y2="35" />
                    </svg>
                </div>
                <h3 style={{ marginTop: '30px', animation: 'pulse-stress 2s infinite alternate' }}>Врата открываются...</h3>
            </div>
        );
    }

    if (!data) return <div style={{ color:'red', textAlign:'center', marginTop:'50px' }}>Failed to load fate.</div>;

    return (
        <div id="app" style={{ paddingBottom: '60px' }}>
            {data.role === 'admin' ? (
                <AdminPanel data={data} onRefresh={loadData} />
            ) : data.role === 'player' ? (
                <PlayerCard data={data} onRollDice={() => setDiceActive(true)} />
            ) : (
                <div className="card" style={{ marginTop: '50px', textAlign: 'center' }}>
                    <h3 style={{ color: '#ff6b6b', fontSize: '1.5rem', marginBottom: '10px' }}>Тень не узнает тебя</h3>
                    <p style={{ color: '#a0a0a0', fontSize: '0.9rem' }}>Человек не найден в свитках судеб.</p>
                </div>
            )}
            
            <DiceRoller active={diceActive} onClose={() => setDiceActive(false)} onFinished={loadData} charId={data.character?.id} />

            <div style={{ position: 'fixed', bottom: '15px', right: '15px', zIndex: 100 }}>
                <button 
                    onClick={() => {
                        const music = document.getElementById('bg-music');
                        if (music) {
                            if (music.paused) {
                                music.play().catch(e => console.log(e));
                                setMusicPlaying(true);
                            } else {
                                music.pause();
                                setMusicPlaying(false);
                            }
                        }
                    }} 
                    style={{ 
                        width: '45px', height: '45px', borderRadius: '50%', padding: 0, 
                        display: 'flex', justifyContent: 'center', alignItems: 'center',
                        background: 'rgba(20, 15, 25, 0.8)', border: '1px solid var(--accent-color)',
                        color: 'var(--accent-color)', fontSize: '1.2rem', boxShadow: '0 0 15px var(--neon-glow)'
                    }}
                >
                    {musicPlaying ? '🔊' : '🔇'}
                </button>
            </div>
        </div>
    );
}
