import { createRoot } from 'react-dom/client'
import { EnterpriseNetworkCard } from '../../src/components/EnterpriseNetworkCard'
import { ServerConnectScreen } from '../../src/components/ServerConnectScreen'
import '../../src/index.css'
import '../../src/App.css'

document.documentElement.dataset.theme = new URLSearchParams(location.search).get('theme') ?? 'light'
createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).has('connect') ? <ServerConnectScreen currentUrl={null} /> : <div className="page panels"><EnterpriseNetworkCard /></div>)
