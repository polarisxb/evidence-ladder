import { getDb } from '../database/db';
import { Email, EmailFolder } from '../types';

interface RawEmail {
  id: string;
  ownerUserId: string;
  folder: EmailFolder;
  fromAddr: string;
  toAddr: string;
  subject: string;
  body: string;
  isRead: number;
  starred: number;
  createdAt: string;
}

const SELECT_COLS = `
  id, owner_user_id as ownerUserId, folder, from_addr as fromAddr,
  to_addr as toAddr, subject, body, is_read as isRead,
  starred, created_at as createdAt
`;

function mapRow(row: RawEmail): Email {
  return { ...row };
}

export function findEmailsByOwner(ownerUserId: string, folder?: EmailFolder): Email[] {
  const db = getDb();
  const rows = folder
    ? db.prepare<[string, string], RawEmail>(`
        SELECT ${SELECT_COLS} FROM emails
        WHERE owner_user_id = ? AND folder = ?
        ORDER BY created_at DESC
      `).all(ownerUserId, folder)
    : db.prepare<[string], RawEmail>(`
        SELECT ${SELECT_COLS} FROM emails
        WHERE owner_user_id = ?
        ORDER BY created_at DESC
      `).all(ownerUserId);
  return rows.map(mapRow);
}

export function findEmailById(emailId: string): Email | null {
  const row = getDb().prepare<[string], RawEmail>(`
    SELECT ${SELECT_COLS} FROM emails WHERE id = ?
  `).get(emailId);
  return row ? mapRow(row) : null;
}

export function searchEmails(ownerUserId: string, query: string): Email[] {
  const like = `%${query}%`;
  const rows = getDb().prepare<[string, string, string], RawEmail>(`
    SELECT ${SELECT_COLS} FROM emails
    WHERE owner_user_id = ?
      AND (subject LIKE ? OR body LIKE ?)
    ORDER BY created_at DESC
  `).all(ownerUserId, like, like);
  return rows.map(mapRow);
}

// Starred emails across all folders (drives the 「星标邮件」 view).
export function findStarredByOwner(ownerUserId: string): Email[] {
  const rows = getDb().prepare<[string], RawEmail>(`
    SELECT ${SELECT_COLS} FROM emails
    WHERE owner_user_id = ? AND starred = 1
    ORDER BY created_at DESC
  `).all(ownerUserId);
  return rows.map(mapRow);
}

export function markEmailRead(emailId: string): boolean {
  const result = getDb().prepare<[string]>(`
    UPDATE emails SET is_read = 1 WHERE id = ?
  `).run(emailId);
  return result.changes > 0;
}

export function setEmailRead(emailId: string, read: boolean): boolean {
  const result = getDb().prepare<[number, string]>(`
    UPDATE emails SET is_read = ? WHERE id = ?
  `).run(read ? 1 : 0, emailId);
  return result.changes > 0;
}

export function setEmailStarred(emailId: string, starred: boolean): boolean {
  const result = getDb().prepare<[number, string]>(`
    UPDATE emails SET starred = ? WHERE id = ?
  `).run(starred ? 1 : 0, emailId);
  return result.changes > 0;
}

export function moveEmailToFolder(emailId: string, folder: EmailFolder): boolean {
  const result = getDb().prepare<[string, string]>(`
    UPDATE emails SET folder = ? WHERE id = ?
  `).run(folder, emailId);
  return result.changes > 0;
}

export function insertSentEmail(
  id: string,
  ownerUserId: string,
  fromAddr: string,
  toAddr: string,
  subject: string,
  body: string,
): void {
  insertEmail(id, ownerUserId, 'sent', fromAddr, toAddr, subject, body, true);
}

// Generic insert used for sent mail and saved drafts.
export function insertEmail(
  id: string,
  ownerUserId: string,
  folder: EmailFolder,
  fromAddr: string,
  toAddr: string,
  subject: string,
  body: string,
  isRead: boolean,
): void {
  const now = new Date().toISOString();
  getDb().prepare<[string, string, string, string, string, string, string, number, string]>(`
    INSERT INTO emails (id, owner_user_id, folder, from_addr, to_addr, subject, body, is_read, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(id, ownerUserId, folder, fromAddr, toAddr, subject, body, isRead ? 1 : 0, now);
}
