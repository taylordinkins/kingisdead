import { useEffect, useState } from "react";
import GameScreen from "./shell/GameScreen";
import Lobby from "./shell/Lobby";

const parseHash = (): string | null => {
  const m = /^#\/game\/(.+)$/.exec(window.location.hash);
  return m?.[1] ? decodeURIComponent(m[1]) : null;
};

export default function App() {
  const [gameId, setGameId] = useState<string | null>(parseHash);

  useEffect(() => {
    const onHash = () => setGameId(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  return (
    <main>
      <h1>The King is Dead</h1>
      {gameId ? (
        <GameScreen
          key={gameId}
          gameId={gameId}
          onExit={() => {
            window.location.hash = "";
          }}
        />
      ) : (
        <Lobby
          onCreated={(id) => {
            window.location.hash = `#/game/${encodeURIComponent(id)}`;
          }}
        />
      )}
    </main>
  );
}
