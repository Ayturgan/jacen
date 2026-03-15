import { useState, useEffect } from 'react';
import { safeFetch, safeTGAction } from '../api';

export default function DiceRoller({ active, charId, onClose, onFinished }) {
    const [result, setResult] = useState(20);
    const [rolling, setRolling] = useState(false);
    const [showText, setShowText] = useState(false);

    useEffect(() => {
        if (!active) {
            setRolling(false);
            setShowText(false);
            return;
        }

        setRolling(true);
        setShowText(false);
        safeTGAction(t => t.HapticFeedback.impactOccurred('heavy'));

        const spinInterval = setInterval(() => {
            setResult(Math.floor(Math.random() * 20) + 1);
        }, 50);

        setTimeout(() => {
            clearInterval(spinInterval);
            setRolling(false);
            
            const finalResult = Math.floor(Math.random() * 20) + 1;
            setResult(finalResult);
            setShowText(true);
            
            safeTGAction(t => t.HapticFeedback.notificationOccurred(
                finalResult === 20 ? 'success' : finalResult === 1 ? 'error' : finalResult >= 10 ? 'success' : 'warning'
            ));
            
            setTimeout(async () => {
                if (charId) {
                    try {
                        await fetch('/api/roll_dice', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ char_id: charId, result: finalResult })
                        });
                    } catch(e) { console.error(e); }
                }
                if (onFinished) onFinished();
                onClose();
            }, 4000); 
            
        }, 1800);

        return () => clearInterval(spinInterval);
    }, [active]);

    if (!active) return null;

    let textStr = `Судьба дарует: ${result}`;
    let textColor = 'var(--accent-hover)';
    let textShadow = '0 0 20px var(--neon-glow)';

    if (result === 20) {
        textStr = '🔥 КРИТИЧЕСКИЙ УСПЕХ';
        textColor = '#50C878';
        textShadow = '0 0 30px rgba(80,200,120,0.8)';
    } else if (result === 1) {
        textStr = '💀 РОКОВОЙ ПРОВАЛ';
        textColor = '#ff4444';
        textShadow = '0 0 30px rgba(255,68,68,0.8)';
    }

    return (
        <div id="dice-container" onClick={onClose} style={{ display: 'flex' }}>
            <h3 className="dice-title">Бросок Судьбы</h3>
            <div className={`d20-wrapper ${rolling ? 'rolling' : ''}`} id="dice-element">
                <div className="d20-spinner">
                    <svg viewBox="0 0 100 100" className="d20-svg">
                        <polygon points="50,5 90,25 90,75 50,95 10,75 10,25" />
                        <polygon points="25,35 75,35 50,80" className="glass-face"/>
                        <line x1="50" y1="5" x2="25" y2="35" />
                        <line x1="50" y1="5" x2="75" y2="35" />
                        <line x1="90" y1="25" x2="75" y2="35" />
                        <line x1="90" y1="75" x2="75" y2="35" />
                        <line x1="90" y1="75" x2="50" y2="80" />
                        <line x1="50" y1="95" x2="50" y2="80" />
                        <line x1="10" y1="75" x2="50" y2="80" />
                        <line x1="10" y1="75" x2="25" y2="35" />
                        <line x1="10" y1="25" x2="25" y2="35" />
                    </svg>
                </div>
                <div className="d20-number" style={{ color: !rolling ? textColor : 'var(--text-color)' }}>
                    {result}
                </div>
            </div>
            <div id="dice-result-text" className={showText ? 'show' : ''} style={{ color: textColor, textShadow: textShadow }}>
                {textStr}
            </div>
        </div>
    );
}
