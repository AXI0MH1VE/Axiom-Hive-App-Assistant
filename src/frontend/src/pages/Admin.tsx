export function Admin() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Admin Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white p-6 rounded shadow">
          <h2 className="font-semibold mb-2">Audit Log</h2>
          <p className="text-gray-600 text-sm">Review system audit entries</p>
        </div>
        <div className="bg-white p-6 rounded shadow">
          <h2 className="font-semibold mb-2">Feedback</h2>
          <p className="text-gray-600 text-sm">User-reported issues queue</p>
        </div>
        <div className="bg-white p-6 rounded shadow">
          <h2 className="font-semibold mb-2">Statistics</h2>
          <p className="text-gray-600 text-sm">System health metrics</p>
        </div>
      </div>
    </div>
  );
}
