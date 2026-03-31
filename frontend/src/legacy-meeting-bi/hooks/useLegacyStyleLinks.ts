import { useEffect } from 'react'

export function useLegacyStyleLinks(urls: string[]) {
  const signature = urls.join('|')

  useEffect(() => {
    const createdLinks = urls.map((href) => {
      const existingLink = document.head.querySelector<HTMLLinkElement>(`link[data-legacy-meeting-bi="true"][href="${href}"]`)
      if (existingLink) {
        return existingLink
      }

      const link = document.createElement('link')
      link.rel = 'stylesheet'
      link.href = href
      link.dataset.legacyMeetingBi = 'true'
      document.head.appendChild(link)
      return link
    })

    return () => {
      createdLinks.forEach((link) => {
        if (link.dataset.legacyMeetingBi === 'true') {
          link.remove()
        }
      })
    }
  }, [signature])
}
