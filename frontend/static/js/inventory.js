document.addEventListener('DOMContentLoaded', function () {

  /* ---------------- Tabs Navigation ---------------- */
  var tabs = document.querySelectorAll('.tab');
  var panels = document.querySelectorAll('.tab-panel');

  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (t) { t.classList.remove('is-active'); });
      panels.forEach(function (p) { p.classList.remove('is-active'); });

      tab.classList.add('is-active');
      var target = document.querySelector('[data-panel="' + tab.dataset.tab + '"]');
      if (target) target.classList.add('is-active');
    });
  });

  /* ---------------- Vehicles: Search + Status Filter ---------------- */
  var vehicleSearch = document.getElementById('vehicleSearch');
  var statusFilter = document.getElementById('statusFilter');

  function applyVehicleFilters() {
    var vehicleRows = document.querySelectorAll('#vehiclesTable tbody tr');
    var term = (vehicleSearch && vehicleSearch.value ? vehicleSearch.value : '').trim().toLowerCase();
    var status = statusFilter ? statusFilter.value : '';

    vehicleRows.forEach(function (row) {
      var rowText = row.textContent.toLowerCase();
      var vinMatch = row.dataset.vin ? row.dataset.vin.toLowerCase().indexOf(term) !== -1 : true;
      var textMatch = !term || rowText.indexOf(term) !== -1;
      var matchesTerm = vinMatch || textMatch;
      
      var matchesStatus = !status || (row.dataset.status && row.dataset.status === status);
      row.style.display = (matchesTerm && matchesStatus) ? '' : 'none';
    });
  }

  if (vehicleSearch || statusFilter) {
    if (vehicleSearch) vehicleSearch.addEventListener('input', applyVehicleFilters);
    if (statusFilter) statusFilter.addEventListener('change', applyVehicleFilters);
  }

  /* ---------------- Vendors: Search + Status Filter ---------------- */
  var vendorSearch = document.getElementById('vendorSearch');
  var vendorStatusFilter = document.getElementById('vendorStatusFilter');

  function applyVendorFilters() {
    var vendorRows = document.querySelectorAll('#vendorsTable tbody tr');
    var term = (vendorSearch && vendorSearch.value ? vendorSearch.value : '').trim().toLowerCase();
    var status = vendorStatusFilter ? vendorStatusFilter.value.toLowerCase() : '';

    vendorRows.forEach(function (row) {
      var rowText = row.textContent.toLowerCase();
      var matchesTerm = !term || rowText.indexOf(term) !== -1;
      var rowStatus = row.dataset.status ? row.dataset.status.toLowerCase() : '';
      var matchesStatus = !status || rowStatus === status;

      row.style.display = (matchesTerm && matchesStatus) ? '' : 'none';
    });
  }

  if (vendorSearch || vendorStatusFilter) {
    if (vendorSearch) vendorSearch.addEventListener('input', applyVendorFilters);
    if (vendorStatusFilter) vendorStatusFilter.addEventListener('change', applyVendorFilters);
  }

  /* ---------------- Purchase Orders: Search + Status Filter ---------------- */
  var poSearch = document.getElementById('poSearch');
  var poStatusFilter = document.getElementById('poStatusFilter');

  function applyPOFilters() {
    var poRows = document.querySelectorAll('#poTable tbody tr');
    var term = (poSearch && poSearch.value ? poSearch.value : '').trim().toLowerCase();
    var status = poStatusFilter ? poStatusFilter.value : '';

    poRows.forEach(function (row) {
      var rowText = row.textContent.toLowerCase();
      var matchesTerm = !term || rowText.indexOf(term) !== -1;
      var rowStatus = row.dataset.status || '';
      var matchesStatus = !status || rowStatus === status;

      row.style.display = (matchesTerm && matchesStatus) ? '' : 'none';
    });
  }

  if (poSearch || poStatusFilter) {
    if (poSearch) poSearch.addEventListener('input', applyPOFilters);
    if (poStatusFilter) poStatusFilter.addEventListener('change', applyPOFilters);
  }

  /* ---------------- Row Dropdown Menus and Actions Handler ---------------- */
  document.addEventListener('click', function (event) {
    var toggle = event.target.closest('[data-menu-toggle]');
    var actionTarget = event.target.closest('.row-menu__dropdown a, .row-menu__dropdown button');

    // Handle clicking the three-dots toggle button
    if (toggle) {
      event.stopPropagation();
      var dropdown = toggle.nextElementSibling;
      
      // Close all other open dropdown menus
      document.querySelectorAll('.row-menu__dropdown').forEach(function (menu) {
        if (menu !== dropdown) {
          menu.classList.remove('is-open');
        }
      });
      
      if (dropdown) {
        // Ensure standard clean structure for Purchase Order dropdowns without duplication
        var row = dropdown.closest('tr');
        if (row && row.closest('#poTable')) {
          dropdown.innerHTML = `
            <a href="#" class="action-view" style="display:block; padding:6px 12px; color:#374151; text-decoration:none;">View details</a>
            <a href="#" class="action-received" style="display:block; padding:6px 12px; color:#374151; text-decoration:none;">Mark as Received</a>
            <a href="#" class="action-pending" style="display:block; padding:6px 12px; color:#374151; text-decoration:none;">Mark as Pending</a>
          `;
        }

        dropdown.classList.toggle('is-open');
      }
      return;
    }

    // Handle clicking options inside the dropdown
    if (actionTarget) {
      event.preventDefault();
      event.stopPropagation();

      var actionText = actionTarget.textContent.trim().toLowerCase();
      var row = actionTarget.closest('tr');
      var cellId = row ? row.querySelector('.cell-id') : null;
      var itemId = cellId ? cellId.textContent.trim() : '';

      // View details action
      if (actionText.includes('view details')) {
        alert('Viewing details for ID: ' + itemId);
      } 
      // Edit vehicle action
      else if (actionText.includes('edit vehicle')) {
        alert('Opening edit modal for vehicle ID: ' + itemId);
      } 
      // Edit vendor action
      else if (actionText.includes('edit vendor')) {
        var vendorName = row ? row.querySelectorAll('td')[1].textContent.trim() : '';
        alert('Opening edit modal for vendor: ' + vendorName);
      } 
      // Remove / Delete item action
      else if (actionText.includes('remove')) {
        if (confirm('Are you sure you want to remove item ' + itemId + '?')) {
          alert('Item ' + itemId + ' removed successfully.');
          if (row) row.remove();
        }
      } 
      // Handle status change directly (Received or Pending)
      else if (actionText.includes('received') || actionText.includes('pending')) {
        var badge = row ? row.querySelector('.badge') : null;
        if (badge) {
          if (actionText.includes('received')) {
            badge.textContent = 'Received';
            badge.style.backgroundColor = '#f0fdf4'; // Green background
            badge.style.color = '#15803d'; // Green text
            alert('Purchase Order has been marked as received.');
          } else if (actionText.includes('pending')) {
            badge.textContent = 'Pending';
            badge.style.backgroundColor = '#fff7ed'; // Orange background
            badge.style.color = '#c2410c'; // Orange text
            alert('Purchase Order status changed to Pending.');
          }
        }
      }

      // Close all dropdown menus after executing an action
      document.querySelectorAll('.row-menu__dropdown').forEach(function (menu) {
        menu.classList.remove('is-open');
      });
      return;
    }

    // Close dropdowns when clicking anywhere outside
    if (!event.target.closest('.row-menu')) {
      document.querySelectorAll('.row-menu__dropdown').forEach(function (menu) {
        menu.classList.remove('is-open');
      });
    }
  });

  /* ---------------- Add Vehicle Modal Handler ---------------- */
  var modal = document.getElementById('addVehicleModal');
  var openBtn = document.getElementById('openAddVehicle');
  var form = document.getElementById('addVehicleForm');

  function openModal() { if (modal) modal.classList.add('is-open'); }
  function closeModal() { if (modal) modal.classList.remove('is-open'); }

  if (openBtn) openBtn.addEventListener('click', openModal);

  if (modal) {
    modal.querySelectorAll('[data-modal-close]').forEach(function (btn) {
      btn.addEventListener('click', closeModal);
    });

    modal.addEventListener('click', function (event) {
      if (event.target === modal) closeModal();
    });
  }

  // Close modal on pressing Escape key
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeModal();
  });

  // Handle Add Vehicle Form submission
  if (form) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      console.log('New vehicle payload:', Object.fromEntries(new FormData(form)));
      closeModal();
      form.reset();
    });
  }

});