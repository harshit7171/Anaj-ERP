import NoteEntryScreen from "./NoteEntryScreen";

export default function CreditNoteEntryScreen(props: { mode: "add" | "modify"; onExit(): void }) {
  return <NoteEntryScreen kind="credit" {...props} />;
}
