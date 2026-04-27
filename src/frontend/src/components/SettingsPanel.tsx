import { useStore } from '../store';

export function SettingsPanel() {
  const { settings, setConversation } = useStore();

  const updateSettings = (key: string, value: any) => {
    useStore.setState({
      settings: { ...settings, [key]: value },
    });
  };

  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-gray-900">Settings</h3>

      <div>
        <label className="flex items-center space-x-2">
          <input
            type="checkbox"
            checked={settings.strictMode}
            onChange={(e) => updateSettings('strictMode', e.target.checked)}
            className="rounded text-blue-500"
          />
          <span className="text-sm text-gray-700">Strict Mode (High confidence only)</span>
        </label>
        <p className="text-xs text-gray-500 mt-1">
          Only answers supported by ≥3 sources; otherwise refuses.
        </p>
      </div>

      <div>
        <label className="block text-sm text-gray-700 mb-1">Sources to retrieve</label>
        <input
          type="range"
          min="1"
          max="10"
          value={settings.topK}
          onChange={(e) => updateSettings('topK', parseInt(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-gray-500">
          <span>1</span>
          <span>{settings.topK}</span>
          <span>10</span>
        </div>
      </div>

      <div className="pt-2 border-t">
        <button
          onClick={() => setConversation(crypto.randomUUID())}
          className="w-full bg-gray-100 hover:bg-gray-200 text-gray-900 py-2 px-4 rounded text-sm"
        >
          New Conversation
        </button>
      </div>
    </div>
  );
}
