import { NextResponse } from 'next/server';
export const runtime = 'nodejs';
export async function POST(req: Request) {
  try {
    const data = await req.formData();
    const file = data.get('file');
    if (!(file instanceof File)) return NextResponse.json({ error: 'Upload a file.' }, { status: 400 });
    if (file.size > 5 * 1024 * 1024) return NextResponse.json({ error: 'Maximum file size is 5 MB.' }, { status: 400 });
    const name = file.name.toLowerCase();
    if (!name.endsWith('.pdf') && !name.endsWith('.docx') && !name.endsWith('.txt')) {
      return NextResponse.json({ error: 'Supported formats: PDF, DOCX, TXT.' }, { status: 400 });
    }
    const buffer = Buffer.from(await file.arrayBuffer());
    let text = '';
    if (name.endsWith('.txt')) text = buffer.toString('utf8');
    else if (name.endsWith('.docx')) {
      const mammoth = await import('mammoth');
      text = (await mammoth.extractRawText({ buffer })).value;
    } else {
      const pdf = (await import('pdf-parse')).default;
      text = (await pdf(buffer)).text;
    }
    text = text.trim().slice(0,20000);
    if (!text) return NextResponse.json({ error: 'No extractable text. Scanned PDFs require OCR and are not yet supported.' }, { status: 422 });
    return NextResponse.json({ text });
  } catch {
    return NextResponse.json({ error: 'Could not parse the file. Try another PDF, DOCX or plain text.' }, { status: 422 });
  }
}
