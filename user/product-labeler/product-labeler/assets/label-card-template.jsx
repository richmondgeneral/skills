/**
 * Product Label Cards with Copy Buttons
 * 
 * Template for generating interactive label cards.
 * Adapt the PRODUCTS array with actual product data.
 * Each field has a copy button for easy transfer to Square listings.
 */

import { useState } from 'react';

// ============================================
// PRODUCT DATA - Replace with actual products
// ============================================
const PRODUCTS = [
  {
    id: 1,
    name: "Lay's Korean Honey Mustard 1.2oz (34g) - Taiwan Import",
    price: "4.99",
    sku: "SNACK-LKH-34",
    size: "1.2oz (34g)",
    origin: "Taiwan Import",
    description: `<p>Experience the <strong>sweet-tangy fusion</strong> of Korean honey mustard that's impossible to find in American stores.</p>
<br>
<p><em>Why Korean Honey Mustard from Taiwan?</em> Just like you'll find Mexican-inspired snacks made throughout North America, Taiwan serves as Asia's snack hub—producing beloved Korean flavors for regional distribution.</p>
<br>
<p><strong>What Makes These Different:</strong> Made with palm oil instead of corn oil, these chips deliver a noticeably crispier, lighter texture than US Lay's. The honey mustard has a more pronounced sweetness balanced with tangy kick.</p>
<br>
<p><strong>Product Details:</strong></p>
<ul>
<li>Flavor: Korean Honey Mustard - sweet honey meets tangy mustard</li>
<li>Size: 1.2oz (34g) bag</li>
<li>Made in Taiwan for Asian markets</li>
<li>Limited import availability</li>
</ul>`
  },
  // Add more products here...
];

// ============================================
// COMPONENT CODE - Generally don't modify below
// ============================================

const CopyButton = ({ text, label }) => {
  const [copied, setCopied] = useState(false);
  
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };
  
  return (
    <button
      onClick={handleCopy}
      className={`px-2 py-1 text-xs rounded transition-all ${
        copied 
          ? 'bg-green-500 text-white' 
          : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
      }`}
    >
      {copied ? '✓ Copied!' : `Copy ${label}`}
    </button>
  );
};

const LabelCard = ({ product }) => {
  const [showHtml, setShowHtml] = useState(false);
  
  return (
    <div className="bg-white rounded-lg shadow-md p-4 mb-4 border border-gray-200">
      {/* Header with Name */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <h3 className="font-bold text-lg text-gray-800 flex-1">{product.name}</h3>
        <CopyButton text={product.name} label="Name" />
      </div>
      
      {/* Quick Info Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-gray-50 p-2 rounded">
          <div className="text-xs text-gray-500 mb-1">Price</div>
          <div className="flex items-center justify-between">
            <span className="font-semibold text-green-600">${product.price}</span>
            <CopyButton text={product.price} label="" />
          </div>
        </div>
        
        <div className="bg-gray-50 p-2 rounded">
          <div className="text-xs text-gray-500 mb-1">SKU</div>
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm">{product.sku}</span>
            <CopyButton text={product.sku} label="" />
          </div>
        </div>
        
        <div className="bg-gray-50 p-2 rounded">
          <div className="text-xs text-gray-500 mb-1">Size</div>
          <div className="flex items-center justify-between">
            <span className="text-sm">{product.size}</span>
            <CopyButton text={product.size} label="" />
          </div>
        </div>
        
        <div className="bg-gray-50 p-2 rounded">
          <div className="text-xs text-gray-500 mb-1">Origin</div>
          <div className="flex items-center justify-between">
            <span className="text-sm">{product.origin}</span>
            <CopyButton text={product.origin} label="" />
          </div>
        </div>
      </div>
      
      {/* Description Section */}
      {product.description && (
        <div className="border-t pt-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">Description</span>
            <div className="flex gap-2">
              <button
                onClick={() => setShowHtml(!showHtml)}
                className="px-2 py-1 text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 rounded"
              >
                {showHtml ? 'Preview' : 'HTML'}
              </button>
              <CopyButton text={product.description} label="Description" />
            </div>
          </div>
          
          {showHtml ? (
            <pre className="text-xs bg-gray-900 text-green-400 p-3 rounded overflow-x-auto whitespace-pre-wrap">
              {product.description}
            </pre>
          ) : (
            <div 
              className="text-sm text-gray-700 prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: product.description }}
            />
          )}
        </div>
      )}
    </div>
  );
};

export default function ProductLabels() {
  const [copyAllStatus, setCopyAllStatus] = useState('');
  
  const copyAllAsCSV = () => {
    const headers = ['Product Name', 'Price', 'Size', 'Origin', 'SKU'];
    const rows = PRODUCTS.map(p => [
      p.name, p.price, p.size, p.origin, p.sku
    ].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    
    navigator.clipboard.writeText(csv);
    setCopyAllStatus('CSV Copied!');
    setTimeout(() => setCopyAllStatus(''), 2000);
  };
  
  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-md p-4 mb-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-gray-800">Product Labels</h1>
              <p className="text-sm text-gray-500">{PRODUCTS.length} items • Click any copy button to grab text</p>
            </div>
            <button
              onClick={copyAllAsCSV}
              className={`px-4 py-2 rounded font-medium transition-all ${
                copyAllStatus 
                  ? 'bg-green-500 text-white' 
                  : 'bg-blue-500 hover:bg-blue-600 text-white'
              }`}
            >
              {copyAllStatus || 'Copy All as CSV'}
            </button>
          </div>
        </div>
        
        {/* Label Cards */}
        {PRODUCTS.map(product => (
          <LabelCard key={product.id} product={product} />
        ))}
      </div>
    </div>
  );
}
