import { useEffect, useState } from "react";
import GameScreen from "./shell/GameScreen";
import ImportButton from "./shell/ImportButton";
import Lobby from "./shell/Lobby";

const parseHash = (): string | null => {
  const m = /^#\/game\/(.+)$/.exec(window.location.hash);
  return m?.[1] ? decodeURIComponent(m[1]) : null;
};

const goTo = (id: string) => {
  window.location.hash = `#/game/${encodeURIComponent(id)}`;
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
          onImported={goTo}
        />
      ) : (
        <>
          <Lobby onCreated={goTo} />
          <ImportButton onImported={goTo} />
        </>
      )}
    </main>
  );
}
