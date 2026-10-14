import { useCallback, useEffect, useMemo, useState } from "react";
import "./App.css";

const NODE_CONFIG = [
  {
    name: "follower-B",
    port: 8001,
  },
  {
    name: "follower-C",
    port: 8002,
  },
  {
    name: "ticket-server",
    port: 8000,
  },
];

function App() {
  const [nodes, setNodes] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [promotingPort, setPromotingPort] = useState(null);
  const [message, setMessage] = useState(null);

  const [title, setTitle] = useState("");
  const [clientId, setClientId] = useState("client-A");
  const [creatingTicket, setCreatingTicket] = useState(false);
  const [updatingTicketId, setUpdatingTicketId] = useState(null);

  const loadCluster = useCallback(async () => {
    try {
      const results = await Promise.all(
        NODE_CONFIG.map(async (node) => {
          try {
            const healthResponse = await fetch(
              `/api/${node.port}/health`
            );

            if (!healthResponse.ok) {
              throw new Error("Health check failed");
            }

            const health = await healthResponse.json();

            const ticketsResponse = await fetch(
              `/api/${node.port}/tickets`
            );

            const ticketData = await ticketsResponse.json();

            return {
              ...node,
              online: true,
              role: health.role,
              status: health.status,
              tickets: ticketData.tickets || [],
              lamport: ticketData.server_lamport ?? 0,
              sequence: ticketData.server_sequence ?? 0,
            };
          } catch {
            return {
              ...node,
              online: false,
              role: "offline",
              status: "offline",
              tickets: [],
              lamport: 0,
              sequence: 0,
            };
          }
        })
      );

      setNodes(results);

      const leader = results.find(
        (node) => node.online && node.role === "leader"
      );

      if (leader) {
        setTickets(leader.tickets);
      } else {
        const availableNode = results.find((node) => node.online);
        setTickets(availableNode?.tickets || []);
      }

      setLoading(false);
    } catch {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCluster();

    const interval = setInterval(loadCluster, 3000);

    return () => clearInterval(interval);
  }, [loadCluster]);

  const leader = useMemo(
    () => nodes.find((node) => node.online && node.role === "leader"),
    [nodes]
  );

  const onlineNodes = nodes.filter((node) => node.online);

  const healthyCount = onlineNodes.length;

  const majorityAvailable = healthyCount >= 2;

  const promoteNode = async (port) => {
    setPromotingPort(port);
    setMessage(null);

    try {
      const response = await fetch(`/api/${port}/promote`, {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Promotion failed");
      }

      setMessage({
        type: "success",
        text: `${data.node_name} is now the leader.`,
      });

      await loadCluster();
    } catch (error) {
      setMessage({
        type: "error",
        text: error.message,
      });
    } finally {
      setPromotingPort(null);
    }
  };

  const createTicket = async (event) => {
    event.preventDefault();

    if (!leader) {
      setMessage({
        type: "error",
        text: "There is no active leader available for writes.",
      });
      return;
    }

    if (!title.trim()) {
      setMessage({
        type: "error",
        text: "Please enter a ticket title.",
      });
      return;
    }

    setCreatingTicket(true);
    setMessage(null);

    const requestId = `ui-${Date.now()}`;

    const currentLamport = leader.lamport || 0;

    try {
      const response = await fetch(
        `/api/${leader.port}/tickets`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            request_id: requestId,
            client_id: clientId.trim() || "client-A",
            title: title.trim(),
            client_lamport: currentLamport + 1,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error || "Ticket creation failed"
        );
      }

      setMessage({
        type: "success",
        text: `Ticket #${data.ticket_id} committed successfully.`,
      });

      setTitle("");

      await loadCluster();
    } catch (error) {
      setMessage({
        type: "error",
        text: error.message,
      });
    } finally {
      setCreatingTicket(false);
    }
  };

  const updateTicketStatus = async (ticketId, newStatus) => {
    if (!leader) {
      setMessage({
        type: "error",
        text: "There is no active leader available for status updates.",
      });
      return;
    }

    const currentTicket = tickets.find(
      (ticket) => ticket.ticket_id === ticketId
    );

    if (!currentTicket || currentTicket.status === newStatus) {
      return;
    }

    setUpdatingTicketId(ticketId);
    setMessage(null);

    try {
      const response = await fetch(
        `/api/${leader.port}/tickets/status`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            ticket_id: ticketId,
            status: newStatus,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Ticket status update failed");
      }

      if (!data.committed) {
        throw new Error("The status update was not committed by the cluster.");
      }

      setMessage({
        type: "success",
        text: `Ticket #${ticketId} status updated to ${newStatus}. ` +
          `${data.successful_replications ?? 0} follower(s) acknowledged.`,
      });

      await loadCluster();
    } catch (error) {
      setMessage({
        type: "error",
        text: error.message || "Ticket status update failed.",
      });
      await loadCluster();
    } finally {
      setUpdatingTicketId(null);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">DISTRIBUTED SYSTEM</p>

          <h1>Help Desk Control Center</h1>

          <p className="subtitle">
            Replicated ticket service with leader failover and recovery
          </p>
        </div>

        <div className="live-status">
          <span className="status-dot" />
          <span>
            {loading ? "Connecting..." : "System Online"}
          </span>
        </div>
      </header>

      <main className="dashboard">
        {message && (
          <div className={`alert ${message.type}`}>
            <span>
              {message.type === "success" ? "✓" : "!"}
            </span>
            {message.text}
          </div>
        )}

        <section className="summary-grid">
          <div className="summary-card">
            <span className="summary-label">CLUSTER</span>
            <strong>3 Nodes</strong>
            <span className="summary-detail">
              {healthyCount}/3 online
            </span>
          </div>

          <div className="summary-card">
            <span className="summary-label">LEADER</span>

            <strong>
              {leader ? leader.port : "None"}
            </strong>

            <span className="summary-detail">
              {leader ? leader.name : "Manual failover required"}
            </span>
          </div>

          <div className="summary-card">
            <span className="summary-label">TICKETS</span>

            <strong>{tickets.length}</strong>

            <span className="summary-detail">
              Replicated tickets
            </span>
          </div>

          <div className="summary-card">
            <span className="summary-label">QUORUM</span>

            <strong>
              {majorityAvailable ? "2/3" : "0/3"}
            </strong>

            <span className="summary-detail">
              {majorityAvailable
                ? "Majority available"
                : "Majority unavailable"}
            </span>
          </div>
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <p className="section-kicker">CLUSTER</p>
              <h2>Node Health</h2>
            </div>

            <span className="cluster-badge">
              {healthyCount} / 3 ONLINE
            </span>
          </div>

          <div className="node-grid">
            {nodes.map((node) => (
              <div
                className={`node-card ${
                  node.role === "leader"
                    ? "leader-card"
                    : ""
                } ${
                  !node.online
                    ? "offline-card"
                    : ""
                }`}
                key={node.port}
              >
                <div className="node-card-top">
                  <div>
                    <span className="node-port">
                      PORT {node.port}
                    </span>

                    <h3>{node.name}</h3>
                  </div>

                  {node.role === "leader" && (
                    <span className="role-badge leader">
                      ★ Leader
                    </span>
                  )}

                  {node.role === "follower" &&
                    node.online && (
                      <span className="role-badge follower">
                        Follower
                      </span>
                    )}

                  {!node.online && (
                    <span className="role-badge offline">
                      Offline
                    </span>
                  )}
                </div>

                <div className="node-status">
                  <span
                    className={`status-dot ${
                      !node.online
                        ? "offline-dot"
                        : ""
                    }`}
                  />

                  {node.online
                    ? "Healthy"
                    : "Unavailable"}
                </div>

                <div className="node-metrics">
                  <div>
                    <span>Tickets</span>
                    <strong>
                      {node.tickets.length}
                    </strong>
                  </div>

                  <div>
                    <span>Lamport</span>
                    <strong>{node.lamport}</strong>
                  </div>

                  <div>
                    <span>Sequence</span>
                    <strong>{node.sequence}</strong>
                  </div>
                </div>

                {node.role === "follower" &&
                  node.online &&
                  !leader && (
                    <button
                      className="secondary-button"
                      onClick={() =>
                        promoteNode(node.port)
                      }
                      disabled={
                        promotingPort === node.port
                      }
                    >
                      {promotingPort === node.port
                        ? "Promoting..."
                        : "Promote to Leader"}
                    </button>
                  )}
              </div>
            ))}
          </div>
        </section>

        <section className="content-grid">
          <div className="panel create-panel">
            <div className="section-heading compact">
              <div>
                <p className="section-kicker">
                  TICKETS
                </p>
                <h2>Create Ticket</h2>
              </div>
            </div>

            <form onSubmit={createTicket}>
              <label>
                Ticket title

                <input
                  type="text"
                  value={title}
                  onChange={(event) =>
                    setTitle(event.target.value)
                  }
                  placeholder="Describe the help desk issue"
                />
              </label>

              <label>
                Client ID

                <input
                  type="text"
                  value={clientId}
                  onChange={(event) =>
                    setClientId(event.target.value)
                  }
                  placeholder="client-A"
                />
              </label>

              <label>
                Request ID

                <input
                  type="text"
                  value="Automatically generated"
                  disabled
                  readOnly
                />
              </label>

              <button
                type="submit"
                className="primary-button"
                disabled={
                  creatingTicket || !leader
                }
              >
                {creatingTicket
                  ? "Creating..."
                  : leader
                    ? "Create Ticket"
                    : "No Leader Available"}
              </button>
            </form>
          </div>

          <div className="panel commit-panel">
            <div className="section-heading compact">
              <div>
                <p className="section-kicker">
                  FAILOVER & RECOVERY
                </p>

                <h2>Cluster Control</h2>
              </div>

              {leader ? (
                <span className="success-badge">
                  LEADER ACTIVE
                </span>
              ) : (
                <span className="warning-badge">
                  FAILOVER REQUIRED
                </span>
              )}
            </div>

            <div className="commit-result">
              <div>
                <span>Current leader</span>

                <strong>
                  {leader
                    ? `:${leader.port}`
                    : "None"}
                </strong>
              </div>

              <div>
                <span>Healthy nodes</span>

                <strong>
                  {healthyCount} / 3
                </strong>
              </div>

              <div>
                <span>Majority</span>

                <strong>
                  {majorityAvailable
                    ? "Available"
                    : "Unavailable"}
                </strong>
              </div>

              <div>
                <span>Cluster tickets</span>

                <strong>{tickets.length}</strong>
              </div>
            </div>

            <div className="commit-message">
              <span className="check-icon">
                {leader ? "✓" : "!"}
              </span>

              <div>
                <strong>
                  {leader
                    ? "Cluster ready for writes"
                    : "Manual leader promotion required"}
                </strong>

                <p>
                  {leader
                    ? `Node ${leader.port} is currently the active leader.`
                    : "Stop the failed leader and promote a healthy follower."}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="section">
          <div className="section-heading">
            <div>
              <p className="section-kicker">
                RECENT ACTIVITY
              </p>

              <h2>Tickets</h2>
            </div>
          </div>

          <div className="ticket-table-wrapper">
            <table className="ticket-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Title</th>
                  <th>Request ID</th>
                  <th>Status</th>
                  <th>Sequence</th>
                  <th>Lamport</th>
                </tr>
              </thead>

              <tbody>
                {tickets.map((ticket) => (
                  <tr key={ticket.ticket_id}>
                    <td className="ticket-id">
                      #{ticket.ticket_id}
                    </td>

                    <td>{ticket.title}</td>

                    <td className="request-id">
                      {ticket.request_id}
                    </td>

                    <td>
                      <div className="ticket-status-control">
                        <span className={`ticket-status status-${ticket.status}`}>
                          {ticket.status}
                        </span>
                        <select
                          aria-label={`Update status for ticket ${ticket.ticket_id}`}
                          value={ticket.status}
                          onChange={(event) =>
                            updateTicketStatus(ticket.ticket_id, event.target.value)
                          }
                          disabled={
                            !leader ||
                            updatingTicketId === ticket.ticket_id
                          }
                        >
                          <option value="open">Open</option>
                          <option value="in_progress">In progress</option>
                          <option value="closed">Closed</option>
                        </select>
                        {updatingTicketId === ticket.ticket_id && (
                          <span className="status-saving">Saving…</span>
                        )}
                      </div>
                    </td>

                    <td>
                      {ticket.server_sequence}
                    </td>

                    <td>
                      {ticket.server_lamport}
                    </td>
                  </tr>
                ))}

                {tickets.length === 0 && (
                  <tr>
                    <td
                      colSpan="6"
                      className="empty-state"
                    >
                      No tickets available.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;