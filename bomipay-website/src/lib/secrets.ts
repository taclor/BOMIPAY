export function maskSecret(secret: string, showChars: number = 4): string {
  if (!secret || secret.length <= showChars) return '****'
  return `${secret.slice(0, showChars)}${'•'.repeat(secret.length - showChars)}`
}
