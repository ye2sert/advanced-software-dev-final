"""
PAMS - Tkinter GUI
Author: Yunus Sert (24015097) and Mackenzie Sawers (24033341)
Group: 37

"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date, timedelta

from database import get_db
from services import (
    AuthService, TenantService, ApartmentService, BillingService,
    MaintenanceService, ReportService, UserService, LocationService,
)
from models import Tenant, Apartment, Lease, MaintenanceRequest


# Login Window
# Yunus Sert

class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PAMS - Login")
        self.geometry("420x300")
        self.resizable(False, False)
        self.configure(bg="#f5f6fa")

        self.db = get_db()
        self.auth = AuthService(self.db)

        header = tk.Label(self, text="Paragon Apartment Management System",
                          font=("Helvetica", 13, "bold"),
                          bg="#f5f6fa", fg="#2f3640")
        header.pack(pady=(25, 4))
        sub = tk.Label(self, text="Staff Login",
                       font=("Helvetica", 10), bg="#f5f6fa", fg="#353b48")
        sub.pack(pady=(0, 20))

        frm = tk.Frame(self, bg="#f5f6fa")
        frm.pack(pady=5)

        tk.Label(frm, text="Username:", bg="#f5f6fa").grid(
            row=0, column=0, sticky="e", padx=6, pady=6)
        self.username_var = tk.StringVar()
        tk.Entry(frm, textvariable=self.username_var, width=28).grid(
            row=0, column=1, pady=6)

        tk.Label(frm, text="Password:", bg="#f5f6fa").grid(
            row=1, column=0, sticky="e", padx=6, pady=6)
        self.password_var = tk.StringVar()
        tk.Entry(frm, textvariable=self.password_var, show="*",
                 width=28).grid(row=1, column=1, pady=6)

        tk.Button(self, text="Log in", command=self.on_login,
                  width=16, bg="#44bd32", fg="white",
                  font=("Helvetica", 10, "bold")).pack(pady=18)

        hint = tk.Label(
            self,
            text="Demo: admin_bristol / admin123   •   manager / manager123",
            font=("Helvetica", 8), bg="#f5f6fa", fg="#7f8fa6")
        hint.pack()

        self.bind("<Return>", lambda e: self.on_login())

    def on_login(self):
        try:
            user = self.auth.login(self.username_var.get().strip(),
                                   self.password_var.get())
            self.destroy()
            MainWindow(self.auth).mainloop()
        except PermissionError as e:
            messagebox.showerror("Login failed", str(e))



# Main Window (tabs shown by permission)
# Mackenzie Sawers

class MainWindow(tk.Tk):
    def __init__(self, auth: AuthService):
        super().__init__()
        self.auth = auth
        self.db = auth.db
        user = auth.current_user
        self.title(f"PAMS - {user.full_name} ({user.role_name()})")
        self.geometry("1050x650")
        self.configure(bg="#f5f6fa")

        # top bar
        bar = tk.Frame(self, bg="#273c75")
        bar.pack(fill="x")
        tk.Label(bar,
                 text=f"  Logged in as {user.full_name}   |   "
                      f"Role: {user.role_name()}",
                 bg="#273c75", fg="white",
                 font=("Helvetica", 11, "bold")).pack(side="left", pady=8, padx=8)
        tk.Button(bar, text="Logout", command=self.on_logout,
                  bg="#e84118", fg="white",
                  font=("Helvetica", 9, "bold")).pack(side="right", padx=10, pady=6)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Add tabs based on permissions
        if user.can("tenant.view"):
            self.nb.add(TenantFrame(self.nb, auth), text="Tenants")
        if user.can("apartment.view"):
            self.nb.add(ApartmentFrame(self.nb, auth), text="Apartments")
        if user.can("invoice.view") or user.can("payment.view") or \
           user.can("invoice.create"):
            self.nb.add(BillingFrame(self.nb, auth), text="Billing")
        if user.can("maintenance.view"):
            self.nb.add(MaintenanceFrame(self.nb, auth), text="Maintenance")
        if (user.can("report.financial") or user.can("report.occupancy")
                or user.can("report.maintenance")):
            self.nb.add(ReportFrame(self.nb, auth), text="Reports")
        if user.can("user.view"):
            self.nb.add(UserFrame(self.nb, auth), text="Users")
        if user.can("business.expand"):
            self.nb.add(LocationFrame(self.nb, auth), text="Locations")

    def on_logout(self):
        self.auth.logout()
        self.destroy()
        LoginWindow().mainloop()



# Helper: table with Treeview

class DataTable(ttk.Frame):
    def __init__(self, master, columns):
        super().__init__(master)
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for c in columns:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=120, anchor="w")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def clear(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    def add_rows(self, rows):
        for r in rows:
            self.tree.insert("", "end", values=r)



# Tenant Frame
# Mackenzie Sawers

class TenantFrame(ttk.Frame):
    def __init__(self, master, auth: AuthService):
        super().__init__(master)
        self.auth = auth
        self.svc = TenantService(auth.db, auth)

        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        if auth.current_user.can("tenant.register"):
            ttk.Button(top, text="Register New Tenant",
                       command=self.open_register).pack(side="left", padx=4)
        if auth.current_user.can("tenant.update"):
            ttk.Button(top, text="Update Selected",
                       command=self.update_selected).pack(side="left", padx=4)
        if auth.current_user.can("tenant.delete"):
            ttk.Button(top, text="Delete Selected",
                       command=self.delete_selected).pack(side="left", padx=4)

        cols = ("ID", "NI Number", "Name", "Phone", "Email",
                "Occupation", "Location")
        self.table = DataTable(self, cols); self.table.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh()

    def refresh(self):
        self.table.clear()
        user = self.auth.current_user
        loc_id = user.location_id if user.role_name() != "Manager" else None
        try:
            rows = self.svc.list_tenants(loc_id)
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e)); return
        # location name lookup
        locs = {r["location_id"]: r["city"] for r in
                self.auth.db.query_all("SELECT location_id, city FROM locations")}
        for r in rows:
            self.table.tree.insert("", "end", values=(
                r["tenant_id"], r["ni_number"], r["full_name"], r["phone"],
                r["email"], r["occupation"], locs.get(r["location_id"], "")))

    def open_register(self):
        dlg = TenantDialog(self, "Register New Tenant")
        self.wait_window(dlg)
        if dlg.result:
            try:
                t = Tenant(None, **dlg.result)
                tid = self.svc.register_tenant(t)
                messagebox.showinfo("Saved", f"Tenant created (id={tid})")
                self.refresh()
            except (ValueError, PermissionError) as e:
                messagebox.showerror("Error", str(e))

    def _selected_id(self):
        sel = self.table.tree.selection()
        if not sel: return None
        return int(self.table.tree.item(sel[0], "values")[0])

    def update_selected(self):
        tid = self._selected_id()
        if tid is None:
            messagebox.showwarning("Select", "Select a tenant first"); return
        new_phone = simpledialog.askstring("Update phone",
                                           "New phone number:", parent=self)
        if not new_phone: return
        try:
            self.svc.update_tenant(tid, phone=new_phone)
            self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))

    def delete_selected(self):
        tid = self._selected_id()
        if tid is None: return
        if not messagebox.askyesno("Confirm", f"Delete tenant {tid}?"): return
        try:
            self.svc.delete_tenant(tid); self.refresh()
        except PermissionError as e:
            messagebox.showerror("Error", str(e))


class TenantDialog(tk.Toplevel):
    def __init__(self, master, title):
        super().__init__(master)
        self.title(title); self.grab_set(); self.resizable(False, False)
        self.result = None
        self.vars = {k: tk.StringVar() for k in
                     ("ni_number", "full_name", "phone", "email",
                      "occupation", "tenant_references")}
        labels = {"ni_number": "NI Number", "full_name": "Full name",
                  "phone": "Phone", "email": "Email",
                  "occupation": "Occupation", "tenant_references": "References"}
        r = 0
        for k, lab in labels.items():
            tk.Label(self, text=lab).grid(row=r, column=0, sticky="e",
                                          padx=6, pady=4)
            tk.Entry(self, textvariable=self.vars[k], width=32).grid(
                row=r, column=1, padx=6, pady=4)
            r += 1
        tk.Label(self, text="Location").grid(row=r, column=0, sticky="e")
        self.loc_var = tk.StringVar()
        db = master.auth.db
        self.locs = db.query_all("SELECT location_id, city FROM locations")
        self.loc_cb = ttk.Combobox(self, textvariable=self.loc_var,
                                   values=[l["city"] for l in self.locs],
                                   state="readonly", width=30)
        self.loc_cb.grid(row=r, column=1, padx=6, pady=4)
        if master.auth.current_user.location_id:
            # preselect user's own city
            for l in self.locs:
                if l["location_id"] == master.auth.current_user.location_id:
                    self.loc_cb.set(l["city"]); break
        r += 1
        tk.Button(self, text="Save", command=self.on_save,
                  bg="#44bd32", fg="white").grid(
            row=r, column=0, columnspan=2, pady=10)

    def on_save(self):
        city = self.loc_var.get()
        loc_id = next((l["location_id"] for l in self.locs
                       if l["city"] == city), None)
        if not loc_id:
            messagebox.showerror("Error", "Choose a location"); return
        try:
            self.result = {k: v.get() for k, v in self.vars.items()}
            self.result["location_id"] = loc_id
            # Validation runs in Tenant.__post_init__ upstream
            Tenant(None, **self.result)   # early-fail validation
            self.destroy()
        except ValueError as e:
            messagebox.showerror("Invalid data", str(e))



# Apartment Frame
# Yunus Sert

class ApartmentFrame(ttk.Frame):
    def __init__(self, master, auth: AuthService):
        super().__init__(master)
        self.auth = auth
        self.svc = ApartmentService(auth.db, auth)
        self.tsvc = TenantService(auth.db, auth)

        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        if auth.current_user.can("apartment.create"):
            ttk.Button(top, text="Add Apartment",
                       command=self.add_apt).pack(side="left", padx=4)
        if auth.current_user.can("lease.create"):
            ttk.Button(top, text="Assign to Tenant",
                       command=self.assign_tenant).pack(side="left", padx=4)
        if auth.current_user.can("lease.terminate"):
            ttk.Button(top, text="Terminate Lease (Early)",
                       command=self.terminate).pack(side="left", padx=4)

        self.table = DataTable(self, ("ID", "City", "Apt #", "Type",
                                      "Bedrooms", "Rent (£)", "Status"))
        self.table.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh()

    def refresh(self):
        self.table.clear()
        u = self.auth.current_user
        lid = u.location_id if u.role_name() != "Manager" else None
        try:
            rows = self.svc.list_apartments(lid)
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e)); return
        for r in rows:
            self.table.tree.insert("", "end", values=(
                r["apartment_id"], r["city"], r["apt_number"], r["apt_type"],
                r["bedrooms"], f"{r['monthly_rent']:.2f}", r["status"]))

    def _selected_id(self):
        sel = self.table.tree.selection()
        if not sel: return None
        return int(self.table.tree.item(sel[0], "values")[0])

    def add_apt(self):
        dlg = ApartmentDialog(self); self.wait_window(dlg)
        if dlg.result:
            try:
                a = Apartment(None, **dlg.result)
                self.svc.register_apartment(a)
                self.refresh()
            except (ValueError, PermissionError) as e:
                messagebox.showerror("Error", str(e))

    def assign_tenant(self):
        aid = self._selected_id()
        if not aid:
            messagebox.showwarning("Select", "Select an apartment first"); return
        # ask tenant id
        tid = simpledialog.askinteger("Tenant", "Tenant ID to assign:",
                                      parent=self)
        if not tid: return
        # ask dates
        start = simpledialog.askstring("Start date",
                                       "Start date (YYYY-MM-DD):",
                                       initialvalue=date.today().isoformat(),
                                       parent=self)
        if not start: return
        end = simpledialog.askstring("End date",
                                     "End date (YYYY-MM-DD):",
                                     initialvalue=(date.today() +
                                                   timedelta(days=365)).isoformat(),
                                     parent=self)
        if not end: return
        # load rent from DB
        apt = self.auth.db.query_one(
            "SELECT monthly_rent FROM apartments WHERE apartment_id = ?", (aid,))
        rent = apt["monthly_rent"]
        try:
            l = Lease(None, tid, aid, start, end, rent * 2, rent)
            lid = self.svc.assign_to_tenant(l)
            messagebox.showinfo("OK", f"Lease #{lid} created")
            self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))

    def terminate(self):
        lid_str = simpledialog.askstring("Lease ID",
                                         "Enter Lease ID to terminate:",
                                         parent=self)
        if not lid_str: return
        try:
            lid = int(lid_str)
        except ValueError:
            messagebox.showerror("Error", "Lease ID must be numeric"); return
        reason = simpledialog.askstring("Reason", "Termination reason:",
                                        parent=self) or ""
        try:
            penalty = self.svc.terminate_lease_early(lid, reason)
            messagebox.showinfo(
                "Terminated",
                f"Lease #{lid} terminated. Penalty applied: £{penalty:.2f} "
                f"(5% of monthly rent).")
            self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))


class ApartmentDialog(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Add Apartment"); self.grab_set()
        self.result = None
        self.vars = {
            "apt_number": tk.StringVar(),
            "apt_type":   tk.StringVar(value="1-Bed"),
            "bedrooms":   tk.StringVar(value="1"),
            "monthly_rent": tk.StringVar(value="1000"),
        }
        r = 0
        for k, lab in [("apt_number", "Apt number"),
                       ("apt_type", "Type (Studio/1-Bed/2-Bed/3-Bed)"),
                       ("bedrooms", "Bedrooms"),
                       ("monthly_rent", "Monthly rent (£)")]:
            tk.Label(self, text=lab).grid(row=r, column=0, sticky="e",
                                          padx=6, pady=4)
            tk.Entry(self, textvariable=self.vars[k], width=24).grid(
                row=r, column=1, padx=6, pady=4)
            r += 1
        # location
        tk.Label(self, text="Location").grid(row=r, column=0, sticky="e")
        self.loc_var = tk.StringVar()
        db = master.auth.db
        self.locs = db.query_all("SELECT location_id, city FROM locations")
        self.cb = ttk.Combobox(self, textvariable=self.loc_var,
                               values=[l["city"] for l in self.locs],
                               state="readonly", width=22)
        self.cb.grid(row=r, column=1, padx=6, pady=4)
        if master.auth.current_user.location_id:
            for l in self.locs:
                if l["location_id"] == master.auth.current_user.location_id:
                    self.cb.set(l["city"]); break
        r += 1
        tk.Button(self, text="Save", command=self.on_save,
                  bg="#44bd32", fg="white").grid(
            row=r, column=0, columnspan=2, pady=10)

    def on_save(self):
        try:
            city = self.loc_var.get()
            loc_id = next((l["location_id"] for l in self.locs
                           if l["city"] == city), None)
            if not loc_id:
                raise ValueError("Select a location")
            self.result = {
                "location_id": loc_id,
                "apt_number":  self.vars["apt_number"].get().strip(),
                "apt_type":    self.vars["apt_type"].get().strip(),
                "bedrooms":    int(self.vars["bedrooms"].get()),
                "monthly_rent": float(self.vars["monthly_rent"].get()),
            }
            self.destroy()
        except Exception as e:
            messagebox.showerror("Invalid data", str(e))



# Billing Frame
# Mackenzie Sawers

class BillingFrame(ttk.Frame):
    def __init__(self, master, auth: AuthService):
        super().__init__(master)
        self.auth = auth
        self.svc = BillingService(auth.db, auth)

        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        if auth.current_user.can("invoice.create"):
            ttk.Button(top, text="Create Invoice",
                       command=self.create_invoice).pack(side="left", padx=4)
        if auth.current_user.can("payment.record"):
            ttk.Button(top, text="Record Payment",
                       command=self.record_payment).pack(side="left", padx=4)
        if auth.current_user.can("latefee.apply"):
            ttk.Button(top, text="Run Late-Fee Job",
                       command=self.run_late_fees).pack(side="left", padx=4)

        self.table = DataTable(self, ("Invoice ID", "Lease", "Amount (£)",
                                      "Issue", "Due", "Status",
                                      "Late Fee (£)"))
        self.table.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh()

    def refresh(self):
        self.table.clear()
        try:
            rows = self.svc.list_invoices()
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e)); return
        for r in rows:
            self.table.tree.insert("", "end", values=(
                r["invoice_id"], r["lease_id"], f"{r['amount']:.2f}",
                r["issue_date"], r["due_date"], r["status"],
                f"{(r['late_fee'] or 0):.2f}"))

    def create_invoice(self):
        try:
            lid = simpledialog.askinteger("Lease ID", "Lease ID:", parent=self)
            if not lid: return
            amt = simpledialog.askfloat("Amount", "Amount (£):", parent=self)
            if amt is None: return
            due = simpledialog.askstring(
                "Due date", "Due date (YYYY-MM-DD):",
                initialvalue=(date.today() + timedelta(days=30)).isoformat(),
                parent=self)
            if not due: return
            iid = self.svc.create_invoice(lid, amt, date.today().isoformat(), due)
            messagebox.showinfo("OK", f"Invoice #{iid} created")
            self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))

    def record_payment(self):
        try:
            sel = self.table.tree.selection()
            if sel:
                iid = int(self.table.tree.item(sel[0], "values")[0])
            else:
                iid = simpledialog.askinteger("Invoice", "Invoice ID:",
                                              parent=self)
                if not iid: return
            amt = simpledialog.askfloat("Amount", "Amount paid (£):",
                                        parent=self)
            if amt is None: return
            self.svc.record_payment(iid, amt)
            messagebox.showinfo("OK", "Payment recorded")
            self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))

    def run_late_fees(self):
        try:
            notifs = self.svc.apply_late_fees()
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e)); return
        if not notifs:
            messagebox.showinfo("Late fees", "No overdue invoices found.")
        else:
            msg = f"{len(notifs)} invoices marked Overdue with 5% late fee:\n\n"
            msg += "\n".join(n["message"] for n in notifs[:10])
            messagebox.showinfo("Late fees", msg)
        self.refresh()



# Maintenance Frame
# Yunus Sert

class MaintenanceFrame(ttk.Frame):
    def __init__(self, master, auth: AuthService):
        super().__init__(master)
        self.auth = auth
        self.svc = MaintenanceService(auth.db, auth)

        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        if auth.current_user.can("maintenance.register"):
            ttk.Button(top, text="Register Request",
                       command=self.register).pack(side="left", padx=4)
        if auth.current_user.can("maintenance.assign"):
            ttk.Button(top, text="Assign Selected",
                       command=self.assign).pack(side="left", padx=4)
        if auth.current_user.can("maintenance.resolve"):
            ttk.Button(top, text="Resolve Selected",
                       command=self.resolve).pack(side="left", padx=4)

        self.table = DataTable(
            self, ("Req ID", "City", "Apt", "Priority", "Status",
                   "Reported", "Description"))
        self.table.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh()

    def refresh(self):
        self.table.clear()
        u = self.auth.current_user
        lid = u.location_id if u.role_name() != "Manager" else None
        try:
            rows = self.svc.prioritise_queue(lid)
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e)); return
        for r in rows:
            self.table.tree.insert("", "end", values=(
                r["request_id"], r["city"], r["apt_number"],
                r["priority"], r["status"], r["reported_date"],
                r["description"]))

    def _selected(self):
        sel = self.table.tree.selection()
        if not sel: return None
        return int(self.table.tree.item(sel[0], "values")[0])

    def register(self):
        aid = simpledialog.askinteger("Apartment", "Apartment ID:",
                                      parent=self)
        if not aid: return
        desc = simpledialog.askstring("Description", "Describe the issue:",
                                      parent=self)
        if not desc: return
        pr = simpledialog.askstring("Priority",
                                    "Priority (Low/Medium/High/Critical):",
                                    initialvalue="Medium", parent=self)
        if not pr: return
        try:
            req = MaintenanceRequest(None, aid, None, desc, pr)
            self.svc.register_request(req)
            self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))

    def assign(self):
        rid = self._selected()
        if not rid:
            messagebox.showwarning("Select", "Select a request"); return
        uid = simpledialog.askinteger(
            "User",
            "Maintenance staff User ID to assign:", parent=self)
        if not uid: return
        try:
            self.svc.assign(rid, uid); self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))

    def resolve(self):
        rid = self._selected()
        if not rid:
            messagebox.showwarning("Select", "Select a request"); return
        try:
            hrs = simpledialog.askfloat("Time", "Hours taken:", parent=self)
            cost = simpledialog.askfloat("Cost", "Cost (£):", parent=self)
            notes = simpledialog.askstring("Notes", "Resolution notes:",
                                           parent=self) or ""
            if hrs is None or cost is None: return
            self.svc.resolve(rid, hrs, cost, notes); self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))



# Reports Frame
# Mackenzie Sawers

class ReportFrame(ttk.Frame):
    def __init__(self, master, auth: AuthService):
        super().__init__(master)
        self.auth = auth
        self.svc = ReportService(auth.db, auth)

        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=6)
        if auth.current_user.can("report.occupancy"):
            ttk.Button(top, text="Occupancy Report",
                       command=self.run_occ).pack(side="left", padx=4)
        if auth.current_user.can("report.financial"):
            ttk.Button(top, text="Financial Report",
                       command=self.run_fin).pack(side="left", padx=4)
        if auth.current_user.can("report.maintenance"):
            ttk.Button(top, text="Maintenance Cost Report",
                       command=self.run_maint).pack(side="left", padx=4)

        self.out = tk.Text(self, wrap="word", font=("Courier", 10),
                           bg="#2f3640", fg="#f5f6fa")
        self.out.pack(fill="both", expand=True, padx=6, pady=6)

    def _print(self, title, data):
        self.out.delete("1.0", "end")
        self.out.insert("end", f"=== {title} ===\n")
        self.out.insert("end", f"Generated at: {data['generated_at']}\n\n")
        if "occupancy_rate" in data:
            self.out.insert("end",
                            f"Overall occupancy: {data['occupancy_rate']}%\n\n")
        for row in data.get("rows", []):
            self.out.insert("end", str(row) + "\n")
        for k in ("collected", "pending"):
            if k in data:
                self.out.insert("end", f"{k.capitalize()}: £{data[k]:,.2f}\n")

    def _loc(self):
        u = self.auth.current_user
        return u.location_id if u.role_name() != "Manager" else None

    def run_occ(self):
        try:
            self._print("Occupancy Report", self.svc.occupancy(self._loc()))
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e))

    def run_fin(self):
        try:
            self._print("Financial Report", self.svc.financial(self._loc()))
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e))

    def run_maint(self):
        try:
            self._print("Maintenance Cost Report",
                        self.svc.maintenance(self._loc()))
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e))



# User Management (Admin)
# Yunus Sert

class UserFrame(ttk.Frame):
    def __init__(self, master, auth: AuthService):
        super().__init__(master)
        self.auth = auth
        self.svc = UserService(auth.db, auth)

        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        if auth.current_user.can("user.create"):
            ttk.Button(top, text="Create User",
                       command=self.create).pack(side="left", padx=4)
        if auth.current_user.can("user.update"):
            ttk.Button(top, text="Deactivate Selected",
                       command=self.deactivate).pack(side="left", padx=4)

        self.table = DataTable(self, ("ID", "Username", "Name", "Email",
                                      "Role", "Location", "Active"))
        self.table.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh()

    def refresh(self):
        self.table.clear()
        u = self.auth.current_user
        lid = u.location_id if u.role_name() != "Manager" else None
        try:
            rows = self.svc.list_users(lid)
        except PermissionError as e:
            messagebox.showerror("Access denied", str(e)); return
        locs = {r["location_id"]: r["city"] for r in
                self.auth.db.query_all("SELECT location_id, city FROM locations")}
        for r in rows:
            self.table.tree.insert("", "end", values=(
                r["user_id"], r["username"], r["full_name"], r["email"],
                r["role"], locs.get(r["location_id"], ""),
                "Yes" if r["active"] else "No"))

    def _sel(self):
        sel = self.table.tree.selection()
        if not sel: return None
        return int(self.table.tree.item(sel[0], "values")[0])

    def create(self):
        uname = simpledialog.askstring("Username", "Username:", parent=self)
        if not uname: return
        pw    = simpledialog.askstring("Password", "Password:",
                                       show="*", parent=self)
        if not pw: return
        fname = simpledialog.askstring("Full name", "Full name:", parent=self)
        if not fname: return
        email = simpledialog.askstring("Email", "Email:", parent=self)
        if not email: return
        role  = simpledialog.askstring(
            "Role",
            "Role (FrontDesk/FinanceManager/MaintenanceStaff/Administrator/Manager):",
            parent=self)
        if not role: return
        try:
            self.svc.create_user(uname, pw, fname, email, role,
                                 self.auth.current_user.location_id)
            self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))

    def deactivate(self):
        uid = self._sel()
        if not uid: return
        try:
            self.svc.deactivate_user(uid); self.refresh()
        except PermissionError as e:
            messagebox.showerror("Error", str(e))



# Locations (Manager - business expansion)
# Yunus Sert

class LocationFrame(ttk.Frame):
    def __init__(self, master, auth: AuthService):
        super().__init__(master)
        self.auth = auth
        self.svc = LocationService(auth.db, auth)

        top = ttk.Frame(self); top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Button(top, text="Expand to New City",
                   command=self.add).pack(side="left", padx=4)
        self.table = DataTable(self, ("ID", "City", "Address", "Created"))
        self.table.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh()

    def refresh(self):
        self.table.clear()
        for r in self.svc.list_locations():
            self.table.tree.insert("", "end", values=(
                r["location_id"], r["city"], r["address"], r["created_at"]))

    def add(self):
        city = simpledialog.askstring("City", "New city:", parent=self)
        if not city: return
        addr = simpledialog.askstring("Address", "Office address:", parent=self)
        if not addr: return
        try:
            self.svc.add_location(city, addr); self.refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror("Error", str(e))

