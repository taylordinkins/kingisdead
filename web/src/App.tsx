import { useEffect, useState } from "react";
import Editor from "./editor/Editor";
import GameScreen from "./shell/GameScreen";
import ImportButton from "./shell/ImportButton";
import Lobby from "./shell/Lobby";

const parseHash = (): string | null => {
  const m = /^#\/game\/(.+)$/.exec(window.location.hash);
  return m?.[1] ? decodeURIComponent(m[1]) : null;
};

const isEditor = () => window.location.hash === "#/editor";

const goTo = (id: string) => {
  window.location.hash = `#/game/${encodeURIComponent(id)}`;
};

export default function App() {
  const [gameId, setGameId] = useState<string | null>(parseHash);
  const [editor, setEditor] = useState(isEditor);

  useEffect(() => {
    const onHash = () => {
      setGameId(parseHash());
      setEditor(isEditor());
    };
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
      ) : editor ? (
        <Editor
          onCreated={goTo}
          onExit={() => {
            window.location.hash = "";
          }}
        />
      ) : (
        <>
          <Lobby onCreated={goTo} onOpenEditor={() => (window.location.hash = "#/editor")} />
          <ImportButton onImported={goTo} />
        </>
      )}
    </main>
  );
}
