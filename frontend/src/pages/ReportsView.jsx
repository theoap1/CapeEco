import { FileText } from 'lucide-react';

export default function ReportsView() {
  return (
    <div className="h-full bg-gray-950 flex items-center justify-center">
      <div className="text-center">
        <div className="w-16 h-16 rounded-2xl bg-gray-800 border border-gray-700 flex items-center justify-center mx-auto mb-4">
          <FileText className="w-8 h-8 text-gray-500" />
        </div>
        <h2 className="text-lg font-semibold text-white mb-2">Reports</h2>
        <p className="text-sm text-gray-500 max-w-sm">
          View and manage your generated Development Potential Reports.
          Select a property from the map to generate a new report.
        </p>
      </div>
    </div>
  );
}
