import Sidebar from './Sidebar'
import TopBar from './TopBar'

interface ShellProps {
  title: string
  subtitle?: string
  onRefresh?: () => void
  isRefreshing?: boolean
  children: React.ReactNode
}

export default function Shell({ title, subtitle, onRefresh, isRefreshing, children }: ShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-[#0a0e1a]">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar title={title} subtitle={subtitle} onRefresh={onRefresh} isRefreshing={isRefreshing} />
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
