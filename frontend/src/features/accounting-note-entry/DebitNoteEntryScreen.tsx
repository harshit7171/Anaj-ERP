import NoteEntryScreen from "./NoteEntryScreen";

export default function DebitNoteEntryScreen(props: { mode: "add" | "modify"; onExit(): void }) {
  return <NoteEntryScreen kind="debit" {...props} />;
}
