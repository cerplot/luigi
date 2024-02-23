var LuigiAPI = (function() {
    function LuigiAPI (urlRoot) {
        this.urlRoot = urlRoot;
    }

    function flatten(response, rootId) {
        var flattened = [];
        // Make the requested stepId the first in the list
        if (rootId && response[rootId]) {
            var rootNode = response[rootId];
            rootNode.stepId=rootId;
            flattened.push(rootNode);
            delete response[rootId];
        }
        $.each(response, function(key, value) {
            value.stepId = key;
            flattened.push(value);
        });
        return flattened;
    }

    function flatten_running(response) {
        $.each(response, function(key, value) {
            value.running = flatten(value.running);
        });
        return response;
    }

    function jsonRPC(url, paramObject, callback) {
        return $.ajax(url, {
            data: {data: JSON.stringify(paramObject)},
            method: "GET",
            success: callback,
            dataType: "json"
        });
    }

    function searchTerm() {
        // FIXME : leaky API.  This shouldn't rely on the DOM.
        if ($('#serverSideCheckbox')[0].checked) {
            return $('#stepTable_filter').find('input').val();
        }
        else {
            return '';
        }
    }

    LuigiAPI.prototype.getDependencyGraph = function (stepId, callback, include_done) {
        return jsonRPC(this.urlRoot + "/dep_graph", {step_id: stepId, include_done: include_done}, function(response) {
            callback(flatten(response.response, stepId));
        });
    };

    LuigiAPI.prototype.getInverseDependencyGraph = function (stepId, callback, include_done) {
        return jsonRPC(this.urlRoot + "/inverse_dep_graph", {step_id: stepId, include_done: include_done}, function(response) {
            callback(flatten(response.response, stepId));
        });
    };

    LuigiAPI.prototype.forgiveFailures = function (stepId, callback) {
        return jsonRPC(this.urlRoot + "/forgive_failures", {step_id: stepId}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.markAsDone = function (stepId, callback) {
        return jsonRPC(this.urlRoot + "/mark_as_done", {step_id: stepId}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.getFailedStepList = function(callback) {
        return jsonRPC(this.urlRoot + "/step_list", {status: "FAILED", upstream_status: "", search: searchTerm()}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.getUpstreamFailedStepList = function(callback) {
        return jsonRPC(this.urlRoot + "/step_list", {status: "PENDING", upstream_status: "UPSTREAM_FAILED", search: searchTerm()}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.getDoneStepList = function(callback) {
        return jsonRPC(this.urlRoot + "/step_list", {status: "DONE", upstream_status: "", search: searchTerm()}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.reEnable = function(stepId, callback) {
        return jsonRPC(this.urlRoot + "/re_enable_step", {step_id: stepId}, function(response) {
            callback(response.response);
        });
    };

    LuigiAPI.prototype.getErrorTrace = function(stepId, callback) {
        return jsonRPC(this.urlRoot + "/fetch_error", {step_id: stepId}, function(response) {
            callback(response.response);
        });
    };

    LuigiAPI.prototype.getStepStatusMessage = function(stepId, callback) {
        return jsonRPC(this.urlRoot + "/get_step_status_message", {step_id: stepId}, function(response) {
            callback(response.response);
        });
    };

    LuigiAPI.prototype.getStepProgressPercentage = function(stepId, callback) {
        return jsonRPC(this.urlRoot + "/get_step_progress_percentage", {step_id: stepId}, function(response) {
            callback(response.response);
        });
    };

    LuigiAPI.prototype.getRunningStepList = function(callback) {
        return jsonRPC(this.urlRoot + "/step_list", {status: "RUNNING", upstream_status: "", search: searchTerm()}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.getBatchRunningStepList = function(callback) {
        return jsonRPC(this.urlRoot + "/step_list", {status: "BATCH_RUNNING", upstream_status: "", search: searchTerm()}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.getPendingStepList = function(callback) {
        return jsonRPC(this.urlRoot + "/step_list", {status: "PENDING", upstream_status: "", search: searchTerm()}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.getDisabledStepList = function(callback) {
        jsonRPC(this.urlRoot + "/step_list", {status: "DISABLED", upstream_status: "", search: searchTerm()}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.getUpstreamDisabledStepList = function(callback) {
        jsonRPC(this.urlRoot + "/step_list", {status: "PENDING", upstream_status: "UPSTREAM_DISABLED", search: searchTerm()}, function(response) {
            callback(flatten(response.response));
        });
    };

    LuigiAPI.prototype.getWorkerList = function(callback) {
        jsonRPC(this.urlRoot + "/worker_list", {}, function(response) {
            callback(flatten_running(response.response));
        });
    };

    LuigiAPI.prototype.getResourceList = function(callback) {
        jsonRPC(this.urlRoot + "/resource_list", {}, function(response) {
            callback(flatten_running(response.response));
        });
    };

    LuigiAPI.prototype.disableWorker = function(workerId) {
        jsonRPC(this.urlRoot + "/disable_worker", {'worker': workerId});
    };

    LuigiAPI.prototype.setWorkerProcesses = function(workerId, n, callback) {
        var data = {worker: workerId, n: n};
        jsonRPC(this.urlRoot + "/set_worker_processes", data, function(response) {
            callback();
        });
    };

    LuigiAPI.prototype.sendSchedulerMessage = function(workerId, stepId, content, callback) {
        var data = {worker: workerId, step: stepId, content: content};
        jsonRPC(this.urlRoot + "/send_scheduler_message", data, function(response) {
            if (callback) {
                callback(response.response.message_id);
            }
        });
    };

    LuigiAPI.prototype.getSchedulerMessageResponse = function(stepId, messageId, callback) {
        var data = {step_id: stepId, message_id: messageId};
        jsonRPC(this.urlRoot + "/get_scheduler_message_response", data, function(response) {
            callback(response.response.response);
        });
    };

    LuigiAPI.prototype.isPauseEnabled = function(callback) {
        jsonRPC(this.urlRoot + '/is_pause_enabled', {}, function(response) {
            callback(response.response.enabled);
        });
    };

    LuigiAPI.prototype.hasStepHistory = function(callback) {
        jsonRPC(this.urlRoot + '/has_step_history', {}, function(response) {
            callback(response.response);
        });
    };

    LuigiAPI.prototype.pause = function() {
        jsonRPC(this.urlRoot + '/pause');
    };

    LuigiAPI.prototype.unpause = function() {
        jsonRPC(this.urlRoot + '/unpause');
    };

    LuigiAPI.prototype.isPaused = function(callback) {
        jsonRPC(this.urlRoot + "/is_paused", {}, function(response) {
            callback(!response.response.paused);
        });
    };

    LuigiAPI.prototype.updateResource = function(resource, n, callback) {
        var data = {'resource': resource, 'amount': n};
        jsonRPC(this.urlRoot + "/update_resource", data, function(response) {
            callback();
        });
    };

    return LuigiAPI;
})();
