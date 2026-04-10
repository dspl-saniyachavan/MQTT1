'use client';

interface PaginationControlsProps {
  currentPage: number;
  totalPages: number;
  itemsPerPage: number;
  totalRecords: number;
  onPageChange: (page: number) => void;
}

export default function PaginationControls({
  currentPage,
  totalPages,
  itemsPerPage,
  totalRecords,
  onPageChange,
}: PaginationControlsProps) {
  const startRecord = totalRecords > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0;
  const endRecord = Math.min(currentPage * itemsPerPage, totalRecords);

  const renderPageNumbers = () => {
    const pages: (number | string)[] = [];

    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);

      if (currentPage > 3) {
        pages.push('...');
      }

      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);

      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      if (currentPage < totalPages - 2) {
        pages.push('...');
      }

      pages.push(totalPages);
    }

    return pages;
  };

  return (
    <div className="px-6 py-4 border-t border-slate-700 bg-slate-700/20">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Records Info */}
        <div className="text-xs text-slate-400 font-medium whitespace-nowrap">
          Showing <span className="text-indigo-400 font-bold">{startRecord}</span> to{' '}
          <span className="text-indigo-400 font-bold">{endRecord}</span> of{' '}
          <span className="text-indigo-400 font-bold">{totalRecords}</span> records
        </div>

        {/* Pagination Buttons */}
        <div className="flex items-center gap-1 flex-wrap justify-center">
          {/* First Page */}
          <button
            onClick={() => onPageChange(1)}
            disabled={currentPage === 1}
            className="px-2 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold transition-colors"
            title="First page"
          >
            ⟨⟨
          </button>

          {/* Previous */}
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold transition-colors"
          >
            ⟨ Prev
          </button>

          {/* Page Numbers */}
          <div className="flex items-center gap-1">
            {renderPageNumbers().map((page, idx) => (
              <button
                key={idx}
                onClick={() => typeof page === 'number' && onPageChange(page)}
                disabled={typeof page === 'string'}
                className={`px-2 py-1 rounded text-xs font-semibold transition-colors ${
                  page === '...'
                    ? 'text-slate-500 cursor-default'
                    : currentPage === page
                    ? 'bg-indigo-600 text-white shadow-lg ring-2 ring-indigo-400/50'
                    : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
                }`}
              >
                {page}
              </button>
            ))}
          </div>

          {/* Next */}
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className="px-3 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold transition-colors"
          >
            Next ⟩
          </button>

          {/* Last Page */}
          <button
            onClick={() => onPageChange(totalPages)}
            disabled={currentPage === totalPages}
            className="px-2 py-1 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 text-slate-300 rounded text-xs font-semibold transition-colors"
            title="Last page"
          >
            ⟩⟩
          </button>
        </div>

        {/* Page Info */}
        <div className="text-xs text-slate-400 font-medium whitespace-nowrap">
          Page <span className="text-indigo-400 font-bold">{currentPage}</span> of{' '}
          <span className="text-indigo-400 font-bold">{totalPages}</span>
        </div>
      </div>
    </div>
  );
}
