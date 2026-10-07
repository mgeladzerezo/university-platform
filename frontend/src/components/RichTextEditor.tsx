"use client";

import { type Editor, EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useTranslations } from "next-intl";

interface Props {
  initialHtml: string;
  editable: boolean;
  labelledBy: string;
  onChange: (html: string) => void;
}

interface ToolbarButton {
  label: string;
  isActive: (editor: Editor) => boolean;
  run: (editor: Editor) => void;
}

const BUTTONS: ToolbarButton[] = [
  {
    label: "bold",
    isActive: (editor) => editor.isActive("bold"),
    run: (editor) => editor.chain().focus().toggleBold().run(),
  },
  {
    label: "italic",
    isActive: (editor) => editor.isActive("italic"),
    run: (editor) => editor.chain().focus().toggleItalic().run(),
  },
  {
    label: "heading",
    isActive: (editor) => editor.isActive("heading", { level: 2 }),
    run: (editor) => editor.chain().focus().toggleHeading({ level: 2 }).run(),
  },
  {
    label: "bulletList",
    isActive: (editor) => editor.isActive("bulletList"),
    run: (editor) => editor.chain().focus().toggleBulletList().run(),
  },
  {
    label: "orderedList",
    isActive: (editor) => editor.isActive("orderedList"),
    run: (editor) => editor.chain().focus().toggleOrderedList().run(),
  },
  {
    label: "quote",
    isActive: (editor) => editor.isActive("blockquote"),
    run: (editor) => editor.chain().focus().toggleBlockquote().run(),
  },
];

export function RichTextEditor({ initialHtml, editable, labelledBy, onChange }: Props) {
  const t = useTranslations("editor.toolbar");
  const editor = useEditor({
    extensions: [StarterKit.configure({ heading: { levels: [2, 3] } })],
    content: initialHtml,
    editable,
    // Next.js renders this component on the server first; TipTap must wait for the client.
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class: "rich-text min-h-48 rounded-b-md border border-slate-400 bg-white px-3 py-2",
        role: "textbox",
        "aria-multiline": "true",
        "aria-labelledby": labelledBy,
      },
    },
    onUpdate: ({ editor: current }) => onChange(current.getHTML()),
  });

  if (!editor) return null;

  return (
    <div>
      <div
        role="toolbar"
        aria-label={t("label")}
        className="flex flex-wrap gap-1 rounded-t-md border border-b-0 border-slate-400 bg-slate-50 p-1"
      >
        {BUTTONS.map((button) => (
          <button
            key={button.label}
            type="button"
            disabled={!editable}
            aria-pressed={button.isActive(editor)}
            onClick={() => button.run(editor)}
            className="rounded px-2 py-1 text-sm text-slate-800 hover:bg-slate-200 disabled:opacity-50 aria-pressed:bg-slate-300"
          >
            {t(button.label)}
          </button>
        ))}
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
