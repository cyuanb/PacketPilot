/** Render task headings and emphasis as React text; never interpret user/model HTML. */
export function MessageBody({ text }: { text: string }) {
  const inline = (line: string) =>
    line
      .split(/(\*\*[^*]+\*\*)/g)
      .map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={i}>{part.slice(2, -2)}</strong>
        ) : (
          part
        ),
      );
  return (
    <div className="message-body agent-message-body">
      {text.split("\n").map((line, i) => {
        if (/^#{1,4}\s/.test(line))
          return <h4 key={i}>{inline(line.replace(/^#{1,4}\s+/, ""))}</h4>;
        if (/^\s*[-*]\s/.test(line))
          return (
            <p className="message-list-line" key={i}>
              • {inline(line.replace(/^\s*[-*]\s+/, ""))}
            </p>
          );
        return line.trim() ? (
          <p key={i}>{inline(line)}</p>
        ) : (
          <div className="message-paragraph-gap" key={i} />
        );
      })}
    </div>
  );
}
